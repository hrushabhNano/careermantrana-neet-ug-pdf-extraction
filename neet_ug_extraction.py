import streamlit as st
import pandas as pd
import re
import logging
import sys
import os
import tempfile
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('parse_selection_list.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger()

# Valid categories for validation
VALID_CATEGORIES = {'OBC', 'SC', 'ST', 'SEBC', 'NTC', 'NTD', 'NTB', 'SBC', 'EWS', 'HA', 'VJA', 'SOBC', 'D1', 'D2', 'D3', 'PWD', 'ORP-C'}

# Function to parse the text file
def parse_text_file(text):
    logger.info("Starting to parse text file")
    lines = text.split('\n')
    data = []
    columns = ['Sr No', 'AIR', 'NEET Roll No.', 'CET Form No.', 'Name', 'Gender', 'Category', 'Quota', 'College Code', 'College Name']
    in_table = False
    skip_next_line = False
    row_count = 0
    skipped_lines = 0

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            logger.debug(f"Line {i+1}: Skipped - empty line")
            skipped_lines += 1
            continue

        logger.debug(f"Line {i+1}: {line}")

        # Detect table start
        if re.match(r'^\s*Sr\.\s+AIR\s+NEET', line) or 'Sr.     AIR     NEET' in line:
            in_table = True
            skip_next_line = True
            logger.info(f"Line {i+1}: Table start detected")
            continue

        # Skip the second header line
        if skip_next_line:
            logger.debug(f"Line {i+1}: Skipped - second header line")
            skipped_lines += 1
            skip_next_line = False
            continue

        # Detect table end
        if 'Legends :' in line:
            in_table = False
            logger.info(f"Line {i+1}: Table end detected (Legends)")
            continue

        # Skip header/footer lines when not in table
        if not in_table and any(line.startswith(x) for x in ['GOVERNMENT', 'Note:', 'Admissions', 'SELECTION', 'Printed', 'I.Q.:']):
            logger.debug(f"Line {i+1}: Skipped - header/footer")
            skipped_lines += 1
            continue

        # Skip Current Selection Details
        if 'Current Selection Details' in line:
            logger.debug(f"Line {i+1}: Skipped - Current Selection Details")
            skipped_lines += 1
            continue

        # Skip dividers
        if line.startswith('----') or line.startswith('===='):
            logger.debug(f"Line {i+1}: Skipped - divider line")
            skipped_lines += 1
            continue

        # Process data rows when in table
        if in_table:
            parts = line.split()
            if not parts or not parts[0].isdigit():
                logger.debug(f"Line {i+1}: Skipped - not a data row (no Sr No)")
                skipped_lines += 1
                continue

            logger.info(f"Line {i+1}: Processing data row: {line}")
            row = {}
            idx = 0

            # Sr No
            if idx < len(parts) and parts[idx].isdigit():
                row['Sr No'] = parts[idx]
                idx += 1
                logger.debug(f"Line {i+1}: Sr No = {row['Sr No']}")
            else:
                logger.warning(f"Line {i+1}: Invalid Sr No, skipping row")
                continue

            # AIR
            if idx < len(parts) and parts[idx].isdigit():
                row['AIR'] = parts[idx]
                idx += 1
                logger.debug(f"Line {i+1}: AIR = {row['AIR']}")
            else:
                logger.warning(f"Line {i+1}: Invalid AIR, skipping row")
                continue

            # NEET Roll No.
            if idx < len(parts) and parts[idx].isdigit():
                row['NEET Roll No.'] = parts[idx]
                idx += 1
                logger.debug(f"Line {i+1}: NEET Roll No. = {row['NEET Roll No.']}")
            else:
                logger.warning(f"Line {i+1}: Invalid NEET Roll No., skipping row")
                continue

            # CET Form No.
            if idx < len(parts) and parts[idx].isdigit():
                row['CET Form No.'] = parts[idx]
                idx += 1
                logger.debug(f"Line {i+1}: CET Form No. = {row['CET Form No.']}")
            else:
                logger.warning(f"Line {i+1}: Invalid CET Form No., skipping row")
                continue

            # Name (collect until Gender)
            name_parts = []
            while idx < len(parts) and parts[idx] not in ['M', 'F']:
                name_parts.append(parts[idx])
                idx += 1
            row['Name'] = ' '.join(name_parts) if name_parts else ''
            logger.debug(f"Line {i+1}: Name = {row['Name']}")

            # Gender
            if idx < len(parts) and parts[idx] in ['M', 'F']:
                row['Gender'] = parts[idx]
                idx += 1
            else:
                row['Gender'] = ''
            logger.debug(f"Line {i+1}: Gender = {row['Gender']}")

            # Category (optional, may include D1/D2/D3/PWD/ORP-C, but not if followed by (W))
            cat = ''
            if idx < len(parts) and parts[idx] in VALID_CATEGORIES:
                # Check if the next part is (W) or similar
                if idx + 1 < len(parts) and re.match(r'^\(W\)$', parts[idx + 1]):
                    # Skip category, move to quota
                    pass
                else:
                    cat = parts[idx]
                    idx += 1
                    if idx < len(parts) and parts[idx] in {'D1', 'D2', 'D3', 'PWD', 'ORP-C'} and cat not in {'D1', 'D2', 'D3', 'PWD', 'ORP-C'}:
                        cat += ' ' + parts[idx]
                        idx += 1
            row['Category'] = cat.strip()
            logger.debug(f"Line {i+1}: Category = {row['Category']}")

            # Quota (collect until College Code or end)
            quota_parts = []
            while idx < len(parts) and not re.match(r'^\d+:', parts[idx]):
                quota_parts.append(parts[idx])
                idx += 1
            quota = ' '.join(quota_parts) if quota_parts else ''
            if quota.startswith('Choice'):
                quota = 'Choice Not Available'
            row['Quota'] = quota
            logger.debug(f"Line {i+1}: Quota = {row['Quota']}")

            # College Code and College Name
            college_code = ''
            college_name = ''
            if idx < len(parts):
                college_parts = ' '.join(parts[idx:]).split(':', 1)
                if len(college_parts) == 2:
                    college_code = college_parts[0].strip()
                    college_name = college_parts[1].strip()
            row['College Code'] = college_code
            row['College Name'] = college_name
            logger.debug(f"Line {i+1}: College Code = {row['College Code']}")
            logger.debug(f"Line {i+1}: College Name = {row['College Name']}")

            # Log the complete row
            logger.info(f"Line {i+1}: Parsed row: {row}")

            # Add row to data
            data.append(row)
            row_count += 1

    logger.info(f"Parsing complete: {row_count} rows parsed, {skipped_lines} lines skipped")
    return pd.DataFrame(data, columns=columns)

# Function to save DataFrame to Excel
def save_to_excel(df, output_file):
    logger.info(f"Saving DataFrame with {len(df)} rows to {output_file}")
    df.to_excel(output_file, index=False, engine='openpyxl')
    logger.info(f"Data saved to {output_file}")
    return output_file

# Function to read logs (limit to last N lines)
def read_logs(log_file, max_lines=1000):
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Return last max_lines lines to avoid overflow
            return ''.join(lines[-max_lines:])
    except Exception as e:
        return f"Error reading log file: {e}"

# Streamlit interface
def main():
    st.title("Career Mantrana: Extract NEET-UG PDF")

    # Custom CSS for fixed-height scrollable logs
    st.markdown("""
        <style>
        .log-container {
            height: 400px;
            overflow-y: scroll;
            background-color: #1e1e1e;
            color: #ffffff;
            font-family: monospace;
            padding: 10px;
            border-radius: 5px;
            border: 1px solid #ddd;
            white-space: pre;
            margin-bottom: 3rem;
        }

        /* Style for Process PDF button */
        div.stButton > button {
        background-color: #8e24aa;
        color: white !important;
        border: none;
        padding: 10px 20px;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 16px;
        margin: 4px 2px;
        cursor: pointer;
        border-radius: 4px;
        }
        div.stButton > button:hover {
            background-color: #6b1a82;
            color: white !important;
        }
        div.stButton > button:active {
            color: white !important;
        }
        /* Style for Browse Files button (file uploader) */
        div.stFileUploader button {
            background-color: #8e24aa;
            color: white !important;
            border: none;
            padding: 10px 20px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 16px;
            margin: 4px 2px;
            cursor: pointer;
            border-radius: 4px;
        }
        div.stFileUploader button:hover {
            background-color: #6b1a82;
            color: white !important;
        }
        div.stFileUploader button:active {
            color: white !important;
        }
        /* Style for Download Cut-off Excel button (download button) */
        div.stDownloadButton > button {
            background-color: #8e24aa;
            color: white !important;
            border: none;
            padding: 10px 20px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 16px;
            margin: 4px 2px;
            cursor: pointer;
            border-radius: 4px;
        }
        div.stDownloadButton > button:hover {
            background-color: #6b1a82;
            color: white !important;
        }
        div.stDownloadButton > button:active {
            color: white !important;
        }  
        </style>
    """, unsafe_allow_html=True)

    # File uploader
    uploaded_file = st.file_uploader("Upload a .txt file converted from https://convertio.co/", type=["txt"])

    if uploaded_file is not None:
        # Read the uploaded file
        try:
            text = uploaded_file.read().decode('utf-8')
            logger.info("Text file uploaded successfully")
        except Exception as e:
            st.error(f"Failed to read uploaded file: {e}")
            logger.error(f"Failed to read uploaded file: {e}")
            return

        # Process the file
        with st.spinner("Processing file..."):
            try:
                df = parse_text_file(text)
                logger.info(f"Parsed DataFrame with {len(df)} rows")

                # Save to a temporary Excel file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                    excel_file = save_to_excel(df, tmp.name)

                # Read and display logs (limited to last 1000 lines)
                st.subheader("Processing Logs")
                logs = read_logs('parse_selection_list.log', max_lines=1000)
                st.markdown(f'<div class="log-container">{logs}</div>', unsafe_allow_html=True)

                # Create two columns for download buttons
                col1, col2 = st.columns(2)
                
                # Download button for full logs
                # with col1:
                #     with open('parse_selection_list.log', 'rb') as f:
                #         st.download_button(
                #             label="Download Full Logs",
                #             data=f,
                #             file_name=f"parse_selection_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
                #             mime="text/plain"
                #         )

                # Download button for Excel
                with col1:
                    with open(excel_file, 'rb') as f:
                        st.download_button(
                            label="Download NEET Excel",
                            data=f,
                            file_name=f"selection_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )

                # Clean up temporary file
                os.unlink(excel_file)

            except Exception as e:
                st.error(f"Processing failed: {e}")
                logger.error(f"Processing failed: {e}")

if __name__ == '__main__':
    main()