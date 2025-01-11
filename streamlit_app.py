import streamlit as st 
import pandas as pd
from ffiec_data_connect import credentials, ffiec_connection, methods
import plotly.express as px  # For pie chart visualization

# Replace with your FFIEC credentials
USERNAME = "cameronkstrong03"
PASSWORD = "AI4aWtaFsaY8TMCyjOsS"

# Load the bank list from the static CSV file
BANKS_CSV_PATH = "banks.csv"  # Ensure this path matches the file's location
banks_data = pd.read_csv(BANKS_CSV_PATH)

# Convert the DataFrame to a list of dictionaries
BANKS = banks_data.to_dict(orient="records")

# Streamlit app
st.title("Bank Construction Loan Analysis")

# State selection
states = sorted(banks_data["state"].unique())
selected_state = st.selectbox("Select State", ["All"] + states)

# County selection (filtered by state)
filtered_counties = (
    banks_data[banks_data["state"] == selected_state]["county"].unique()
    if selected_state != "All"
    else banks_data["county"].unique()
)
selected_county = st.selectbox("Select County", ["All"] + sorted(filtered_counties))

# City selection (filtered by state and county)
filtered_cities = (
    banks_data[(banks_data["state"] == selected_state) & (banks_data["county"] == selected_county)]["city"].unique()
    if selected_state != "All" and selected_county != "All"
    else banks_data[banks_data["state"] == selected_state]["city"].unique()
    if selected_state != "All"
    else banks_data["city"].unique()
)
selected_city = st.selectbox("Select City", ["All"] + sorted(filtered_cities))

# Reporting period input
reporting_period = st.text_input("Enter Reporting Period (e.g., 6/30/2024)", "6/30/2024")

# Filter banks based on selections
filtered_banks = [
    bank
    for bank in BANKS
    if (selected_state == "All" or bank["state"] == selected_state)
    and (selected_county == "All" or bank["county"] == selected_county)
    and (selected_city == "All" or bank["city"] == selected_city)
]

# Display filtered banks for user confirmation
st.write(f"### Selected Banks ({len(filtered_banks)} total)", pd.DataFrame(filtered_banks))

# Preserve results in session state
def run_analysis():
    # Initialize FFIEC connection
    creds = credentials.WebserviceCredentials(username=USERNAME, password=PASSWORD)
    conn = ffiec_connection.FFIECConnection()

    results = []
    for bank in filtered_banks:
        try:
            time_series = methods.collect_data(
                session=conn,
                creds=creds,
                rssd_id=bank["rssd_id"],
                reporting_period=reporting_period,
                series="call"
            )

            # Filter for RCONF158 and RCONF159
            rconf158_data = next((item for item in time_series if item.get("mdrm") == "RCONF158"), None)
            rconf159_data = next((item for item in time_series if item.get("mdrm") == "RCONF159"), None)

            # Extract values
            rconf158_value = (rconf158_data.get("int_data", 0) * 1000) if rconf158_data else 0
            rconf159_value = (rconf159_data.get("int_data", 0) * 1000) if rconf159_data else 0
            total_construction_loans = rconf158_value + rconf159_value

            results.append({
                "Bank Name": bank["name"],
                "City": bank["city"],
                "State": bank["state"],
                "County": bank["county"],
                "1-4 Family Residential Construction Loans ($)": rconf158_value,
                "Other Construction and Land Development Loans ($)": rconf159_value,
                "Total Construction Loans ($)": total_construction_loans,
            })
        except Exception as e:
            st.error(f"Error analyzing {bank['name']}: {e}")
            results.append({
                "Bank Name": bank["name"],
                "City": bank["city"],
                "State": bank["state"],
                "County": bank["county"],
                "1-4 Family Residential Construction Loans ($)": "Error",
                "Other Construction and Land Development Loans ($)": "Error",
                "Total Construction Loans ($)": "Error",
            })

    return pd.DataFrame(results)

if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None
if "chart_option" not in st.session_state:
    st.session_state.chart_option = "Total Construction Loans ($)"

if st.button("Run Analysis"):
    if not filtered_banks:
        st.warning("No banks match the selected filters.")
    else:
        st.session_state.analysis_results = run_analysis()

# Display results
if st.session_state.analysis_results is not None:
    df = st.session_state.analysis_results
    st.write("### Analysis Results")
    st.write("*Note: All amounts are presented in ones ($).*")
    st.dataframe(df)

    # Pie chart visualization for construction loans
    st.write("### Construction Loans Distribution")
    st.session_state.chart_option = st.selectbox(
        "Select Loan Type for Pie Chart",
        ["Total Construction Loans ($)", "1-4 Family Residential Construction Loans ($)", "Other Construction and Land Development Loans ($)"]
    )
    try:
        pie_chart = px.pie(
            df,
            names="Bank Name",
            values=st.session_state.chart_option,
            title=f"{st.session_state.chart_option} by Bank",
            hole=0.4,
        )
        st.plotly_chart(pie_chart)
    except Exception as e:
        st.error(f"Error creating the pie chart: {e}")

    # Top 10 lenders table
    st.write("### Top 10 Lenders by Loan Size")
    try:
        df_filtered = df[df[st.session_state.chart_option].apply(lambda x: isinstance(x, (int, float)))]
        top_10 = df_filtered[["Bank Name", st.session_state.chart_option]].sort_values(by=st.session_state.chart_option, ascending=False).head(10).reset_index(drop=True)
        top_10.insert(0, "Rank", range(1, len(top_10) + 1))  # Add Rank column
        top_10 = top_10[["Rank", "Bank Name", st.session_state.chart_option]]  # Ensure only 3 columns
        st.write(f"Top 10 Lenders for {st.session_state.chart_option}")
        st.dataframe(top_10, use_container_width=True)
    except Exception as e:
        st.error(f"Error creating the top 10 table: {e}")

    # Option to download results
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Results as CSV",
        data=csv,
        file_name="bank_analysis_results.csv",
        mime="text/csv",
    )
