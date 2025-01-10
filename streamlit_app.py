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

# Run analysis
if st.button("Run Analysis"):
    if not filtered_banks:
        st.warning("No banks match the selected filters.")
    else:
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
                    "1-4 Family Residential Construction Loans (RCONF158)": rconf158_value,
                    "Other Construction and Land Development Loans (RCONF159)": rconf159_value,
                    "Total Construction Loans": total_construction_loans,
                })
            except Exception as e:
                st.error(f"Error analyzing {bank['name']}: {e}")
                results.append({
                    "Bank Name": bank["name"],
                    "City": bank["city"],
                    "State": bank["state"],
                    "County": bank["county"],
                    "1-4 Family Residential Construction Loans (RCONF158)": "Error",
                    "Other Construction and Land Development Loans (RCONF159)": "Error",
                    "Total Construction Loans": "Error",
                })

        # Display results
        if results:
            df = pd.DataFrame(results)
            st.write("### Analysis Results")
            st.write("*Note: All amounts are presented in ones (not thousands).*")
            st.dataframe(df)

            # Pie chart visualization for Total Construction Loans
            st.write("### Total Construction Loans Distribution")
            try:
                pie_chart = px.pie(
                    df,
                    names="Bank Name",
                    values="Total Construction Loans",
                    title="Total Construction Loans by Bank",
                    hole=0.4,
                )
                st.plotly_chart(pie_chart)
            except Exception as e:
                st.error(f"Error creating the pie chart: {e}")

            # Option to download results
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download Results as CSV",
                data=csv,
                file_name="bank_analysis_results.csv",
                mime="text/csv",
            )