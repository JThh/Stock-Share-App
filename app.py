import certifi
from datetime import datetime

import streamlit as st
import streamlit_authenticator as stauth
import pandas as pd
import pymongo
import matplotlib.pyplot as plt
import yaml

from yaml.loader import SafeLoader

# Set page configuration
st.set_page_config(
    page_title="Stock Dashboard App",
    page_icon="📈",
    layout="wide",
)

now = datetime.now()
date = now.strftime("%Y-%m-%d")

with open('./config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
    config['preauthorized']
)

# Initialize connection.
# Uses st.cache_resource to only run once.
@st.cache_resource
def init_connection():
    return pymongo.MongoClient(**st.secrets["mongo"], tlsCAFile=certifi.where())

client = init_connection()

def create_new_user(name):
    db = client.stockdb
    db.status.insert_one({"name": name, "level": "employee", "num_level": 1})
    db.example.insert_one({"name": name, 
                           "initial_shares": 1,
                           "current_value": 1,
                           "growth_percentage": 0,
                           "history": [
                               {"date": date, "shares": 1},
                           ]})
    
def get_latest_share_value():
    db = client.stockdb
    return int(float(list(db.value.find().sort("date", 1).limit(1))[0]['value']))

def update_latest_share_value(value: int):
    db = client.stockdb
    latest_date = list(db.value.find().sort("date", 1).limit(1))[0]['date']
    if latest_date == date:
        query = { "date":  date}
        values = { "$set": { "value": value } }
        db.value.update_one(query, values)
    else:
        db.value.insert_one({"value": value, "date": date,})

# @st.cache_data(ttl=600)
def get_status(name):
    try:
        db = client.stockdb
        items = db.status.find_one({"name": name})
        return items["level"]
    except:
        return None
    
def get_level(name):
    try:
        db = client.stockdb
        items = db.status.find_one({"name": name})
        return int(items["num_level"])
    except:
        return 1

def get_all_names():
    db = client.stockdb
    names = db.example.distinct("name")
    return names

def get_all_data():
    db = client.stockdb
    names = db.example.find()
    return list(names)

# def get_all_shares():
#     db = client.stockdb
#     shares = list(db.example.find("current_value"))[0]
#     return shares

def get_num_shares():
    db = client.stockdb
    agg = db.example.aggregate([{"$group": {"_id": None, "sum":{"$sum":"$current_value"}}}])
    return int(list(agg)[0]['sum'])

def get_total_intended_shares():
    db = client.stockdb
    return int(float(list(db.share.find().sort("date", 1).limit(1))[0]['share']))
    
# @st.cache_data(ttl=600)
def get_employee_data(name):
    db = client.stockdb
    items = db.example.find_one({"name": name})
    return items

def update_user_name(oldname: str, name: str):
    db = client.stockdb
    query = { "name":  oldname}
    values = { "$set": { "name": name } }
    db.status.update_one(query, values)
    db.example.update_one(query, values)

def update_employee_level(name: str, level: int):
    db = client.stockdb
    query = { "name":  name}
    values = { "$set": { "num_level": level} }
    db.status.update_one(query, values)

def update_employee_shares(name: str, shares: int):
    db = client.stockdb
    query = { "name":  name}
    values = { "$set": { "current_value": shares} ,
              "$push": { "history": {
        "date": date, "shares": shares
    } }}
    db.example.update_one(query, values)
    
def update_total_shares(shares: int):
    db = client.stockdb
    try:
        query = { "date":  date}
        values = { "$set": { "share": shares } }
        db.share.update_one(query, values)
    except:
        db.share.insert_one({"date": date, "share": shares})

# Login functionality
def login():
    name, authentication_status, username = authenticator.login('Login', 'sidebar')
    if authentication_status:
        authenticator.logout('Logout', 'sidebar', key='unique_key')        
        level = get_status(name)
        if not level:
            try:
                create_new_user(name)
                level = get_status(name)
            except:
                st.warning("User not found in database!")
                st.stop()
        if level.lower().startswith("employee"):
            st.success(f'Welcome *Employee {name}!*')
            employee_dashboard(name)
        elif level.lower().startswith("manager"):
            st.success(f'Welcome *Manager {name}!*')
            manager_dashboard(name)
    elif authentication_status is False:
        st.error('Username/password is incorrect')
    elif authentication_status is None:
        st.warning('Please enter your username and password')
    
    option = st.sidebar.selectbox("Select a service:", ['Select Below if Necessary','Register new user', 'Reset password'], index=0)
    
    if option == 'Register new user':
        try:
            if authenticator.register_user('Register user', 'sidebar', preauthorization=False):
                st.sidebar.success('User registered successfully')
        except Exception as e:
            st.sidebar.error(e)

    elif option == 'Reset password':
        if authentication_status:
            try:
                if authenticator.reset_password(username, 'Reset password', 'sidebar'):
                    st.sidebar.success('Password modified successfully')
            except Exception as e:
                st.sidebar.error(e)


def get_next_largest_number(n):
    # Determine the number of digits in n
    num_digits = len(str(n))

    # Create the string representation of the target number
    target_number = "1" + "0" * num_digits

    # Convert the string to an integer
    next_largest_number = int(target_number)

    return next_largest_number

# Plot stock share history
def plot_stock_history(df):
    df = df.set_index("date")
    fig, ax = plt.subplots()
    ax.plot(df.index, df["shares"], marker="o")
    ax.set_xlabel("Date")
    ax.set_ylabel("Shares")
    plt.tight_layout()
    plt.xticks(rotation=45)
    plt.figure(figsize=(8, 6))
    st.pyplot(fig)

# Employee dashboard
def employee_dashboard(employee_name):
    st.title("Employee Dashboard")
    employee_data = get_employee_data(employee_name)

    st.sidebar.title("Employee User Guide")
    st.sidebar.markdown(
        """
        <style>
        .guide {
            font-size: 16px;
            line-height: 1.6;
            padding: 20px;
            border-radius: 8px;
        }
        </style>
        <div class="guide" style="background-color: #eef4ff; color: #333333">
        <p>This app your currently held shares and the total values, as well as the number of shares growth over time.</p>
        <p>Email your manager to request a share review.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.subheader(f"Employee: {employee_name}")
    st.write(f"Current Shares: {format(employee_data['current_value'],',')}")
    st.write(f"Current Value: ${format(employee_data['current_value'] * get_latest_share_value(),',')}")
    df = pd.DataFrame(employee_data["history"])
    df["date"] = pd.to_datetime(df["date"],format='mixed')
    span = max(1, (df["date"].max() - df["date"].min()).days)
    if span > 1:
        growth = (employee_data['current_value'] - employee_data['initial_shares']) * 100 / \
                    (employee_data['initial_shares'] * span)
        st.write(f"Growth Percentage (per day): {growth:.2f}%")

    if "history" in employee_data:
        st.subheader(f"Stock Share History for {employee_name}")
        plot_stock_history(df)
    
    with st.expander("Request a Share Review"):
        subject = "Request a Share Review"
        contents = st.text_area("Email manager for a review: ", value=f"""Dear Manager,
                            This is {employee_name}, and I am writing to request a stock-share review. Please kindly help me with this. Thanks! """)
        manager_email = "youy@comp.nus.edu.sg"
        cc_email = "ybl@hpcaitech.com"
        subject += f"by {employee_name}"
        st.markdown(f"<a href='mailto:{manager_email}?cc={cc_email}&subject={subject}&body={contents}'>Send Email to {manager_email}</a>", 
                    unsafe_allow_html=True)

# Manager dashboard
def manager_dashboard(mgr_name):
    # add user guide content to sidebar
    st.sidebar.title("Manager User Guide")
    st.sidebar.markdown(
        """
        <style>
        .guide {
            font-size: 16px;
            line-height: 1.6;
            padding: 20px;
            border-radius: 8px;
        }
        </style>
        <div class="guide" style="background-color: #eef4ff; color: #333333">
        <p>This app lists all employee held shares and their total values, as well as the number of shares growth over time.</p>
        <h3>Follow these steps to use the app:</h3>
        <ol>
            <li>Select one of employees from the dropdown list to inspect.</li>
            <li>Navigate between individual and grand view for a better idea of employee held shares.</li>
            <li>Adjust the value per share, employee-held shares, as well as employee level and save to database.</li>
            <li>Log out the app.</li>
        </ol>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    st.title("Manager Dashboard")
    
    col1, col2 = st.columns(2)
    with col1:
        prev_vps = get_latest_share_value()
        max_vps = get_next_largest_number(prev_vps) + 2
        vps = st.slider("Edit value per share ($)", min_value=1, max_value=max_vps, step=1,
                                value=prev_vps)
        st.write(f"Current value per share: ${format(vps, ',')}")
        # if st.button(f"Save value per share"):
        update_latest_share_value(vps)
            # st.success("New share value saved!")
            # st.balloons()
    with col2:
        total_nsr = get_total_intended_shares()
        prev_nsr = get_num_shares()
        max_nsr = get_next_largest_number(total_nsr) + 2
        st.session_state.nsr = st.slider(f"Intended total shares (as of {date})", min_value=1, max_value=max_nsr, step=1,
                                value=total_nsr)
        st.write(f"Number of shares unallocated (or underflow): {format(st.session_state.nsr-prev_nsr,',')}")
        # if st.button(f"Save number of shares"):
        update_total_shares(st.session_state.nsr)
            # st.success("New number of shares saved!")
            # st.balloons()

    tab1, tab2 = st.tabs(['Individual View', 'Grand View'])
    with tab1:
        names = get_all_names()
        names = [name for name in names if not get_status(name).startswith('Manager')]
        employee_name = st.selectbox("Select an employee to view", options=names)
        employee_share = get_employee_data(employee_name)

        st.subheader(f"Employee: {employee_name}")
        st.write(f"Current Shares: {format(employee_share['current_value'], ',')}")
        st.write(f"Current Value: ${format(employee_share['current_value'] * vps, ',')}")
        
        df = pd.DataFrame(employee_share["history"])
        df["date"] = pd.to_datetime(df["date"], format='mixed')
        span = max(1, (df["date"].max() - df["date"].min()).days)
        if span > 1:
            growth = (employee_share['current_value'] - employee_share['initial_shares']) * 100 / \
                        (employee_share['initial_shares'] * span)
            st.write(f"Growth Percentage (per day): {growth:.2f}%")

        if "history" in employee_share:
            st.subheader(f"Stock Share Growth History for {employee_name}")
            plot_stock_history(df)
            
        with st.expander("Edit Employee Shares", expanded=True):
            col1, col2 = st.columns(2)
            share = old_share = employee_share['current_value']
            def shr_on_change(share):
                st.session_state.nsr -= (share - old_share)
        
            share = col1.number_input("Enter new share", min_value=0, max_value=st.session_state.nsr - old_share,step=1,
                                value=int(employee_share['current_value']), on_change=shr_on_change, args=(share,))
            level = col2.number_input(f"Update employee level (Current: level {get_level(employee_name)})", 
                                    min_value=1, max_value=10, step=1, value=get_level(employee_name), 
                                    help="Maximum level is 10.")
            if st.button("Save Changes Permanently"):
                with st.spinner("Saving changes..."):
                    if share != employee_share['current_value']:
                        update_employee_shares(employee_name, share)
                    if level:
                        update_employee_level(employee_name, level)
                        
                st.success("Changes to Employee Shares Saved!")
                st.balloons()

    with tab2:
        data = get_all_data()
        tdf = pd.DataFrame(data)
        tdf = tdf[['name', 'current_value', 'history']]
        tdf['history'] = tdf['history'].apply(lambda x:[x[0]['shares'] for x_ in x][-3:])
        tdf['amount'] = tdf['current_value'] * get_latest_share_value()
        tdf['amount'] = tdf['amount'].apply(lambda x:'$'+format(x, ','))
        tdf = tdf[['name', 'amount', 'current_value', 'history']]
        
        st.data_editor(
            tdf,
            column_config={
                "current_value": st.column_config.NumberColumn(
                    "Number of Shares",
                ),
                "name": st.column_config.TextColumn(
                    "Employee Name",
                ),
                "amount": st.column_config.TextColumn(
                    "Total Amount",
                ),
            },
            hide_index=True,
            disabled=True
        )

st.header("HPC-AI Tech Stock Management Systems")
st.sidebar.image("./logo.png", use_column_width=True)
login()

with open('./config.yaml', 'w') as file:
    yaml.dump(config, file, default_flow_style=False)
