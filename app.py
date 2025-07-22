#OCR MVP by Cole Stevens

import streamlit as st
from google.cloud import vision
import gspread
from google.oauth2 import service_account
from datetime import datetime

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/cloud-platform"
]

creds = service_account.Credentials.from_service_account_info(
    st.secrets["service_account"],
    scopes=SCOPES
)

st.write("✅ Auth loaded successfully!")

# === CLIENTS ===
vision_client = vision.ImageAnnotatorClient(credentials=creds)
gspread_client = gspread.authorize(creds)

try:
    sheet = gspread_client.open_by_key("1e0nRervgGaQrB5YK94J24R2vIVKY_5wsX3V6Vt_ITDY").sheet1
    st.write("✅ Google Sheet connected successfully!")
except Exception as e:
    st.error(f"❌ Error connecting to Google Sheets: {e}")

# === Functions ===
def extract_text_from_image(image_bytes):
    image = vision.Image(content=image_bytes)
    response = vision_client.text_detection(image=image)
    if response.error.message:
        raise Exception(f"API Error: {response.error.message}")
    return response.text_annotations[0].description if response.text_annotations else None

def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["app_password"]:
            st.session_state["password_correct"] = True
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Enter Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Enter Password", type="password", on_change=password_entered, key="password")
        st.error("😬 Incorrect password")
        return False
    else:
        return True

def parse_ocr_text(ocr_text):
    sample_id = None
    ingredients = []
    capture = False
    lines = ocr_text.split('\n')

    stop_triggers = ['contains', 'allergen', 'distributed by', 'may contain', 'certified organic', '©', '™', '/', 'tm']

    buffer = []

    for idx, line in enumerate(lines):
        line_lower = line.lower()

        if 'sample id' in line_lower:
            if ':' in line:
                sample_id = line.split(':', 1)[-1].strip()
            elif idx + 1 < len(lines):
                next_line = lines[idx + 1].strip()
                if next_line:
                    sample_id = next_line

        if line_lower.startswith('ingredients'):
            ingredients_part = line.split(':', 1)[-1].strip()
            if ingredients_part:
                buffer.append(ingredients_part)
            capture = True
            continue

        if capture:
            if any(trigger in line_lower for trigger in stop_triggers):
                capture = False
                continue
            elif line.strip():  # Non-empty line
                buffer.append(line.strip())
            else:  # Empty line — treat as potential break but do nothing
                continue

    if buffer:
        ingredients = ' '.join(buffer).replace('  ', ' ')
    else:
        ingredients = None

    return sample_id, ingredients

# === Google Sheets Integration Functions ===
def add_to_google_sheet(sample_id, ingredients):
    existing_ids = sheet.col_values(2)  # Column B (Sample ID)
    if sample_id in existing_ids:
        st.error("❌ Sample ID already exists. Use 'Update Existing Row' instead.")
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([timestamp, sample_id or "Not Found", ingredients or "Not Found"])
        st.success("✅ Added to Google Sheets!")

def update_existing_row(sample_id, ingredients):
    existing_ids = sheet.col_values(2)
    if sample_id in existing_ids:
        row_index = existing_ids.index(sample_id) + 1  # +1 for 1-based index
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.update(f'A{row_index}:C{row_index}', [[timestamp, sample_id or "Not Found", ingredients or "Not Found"]])
        st.success("✅ Existing row updated successfully.")
    else:
        st.warning("⚠️ Sample ID not found. Please use 'Add to Google Sheets' instead.")

# === Streamlit App ===
def main():
    st.title("📄 Product OCR Extractor")
    
    st.markdown("""
    ### 📝 How to Use This Tool
    - Ensure the **entire ingredient block** is clearly visible and in focus.
    - Write the **Sample ID** on a sticky note placed next to the ingredient list.
    - Upload the image using the uploader below.
    - You can edit the extracted text before saving to the database. 
    
    ### 🔒 Internal Tool — For Authorized Team Use Only  
    
    ---
    """)

    col1, col2 = st.columns(2)

    with col1:
        st.image("static/ocr_sample_image_2.jpg", caption="✅ Example of a good image", width=200)
        
    with col2:
        st.image("static/ocr_sample_image_3.jpg", caption="✅ Example of a good image", width=200)

    uploaded_file = st.file_uploader("Upload product image (JPG, PNG)", type=["jpg", "jpeg", "png"])

    if uploaded_file:
        image_bytes = uploaded_file.read()
        try:
            ocr_text = extract_text_from_image(image_bytes)
            if ocr_text:
                # Editable text area for OCR text
                edited_text = st.text_area("🔹 Raw OCR Text (editable):", ocr_text, height=400)

                # Parse the edited text (not the original)
                sample_id, ingredients = parse_ocr_text(edited_text)

                st.success(f"✅ Sample ID: {sample_id or 'Not Found'}")
                st.success(f"✅ Ingredients: {ingredients or 'Not Found'}")

                if st.button("Add to Google Sheets"):
                    if not sample_id or sample_id.strip().lower() == "not found":
                        st.error("❗ Please make sure the **Sample ID** is clearly visible and resubmit the image.")
                    else:
                        add_to_google_sheet(sample_id, ingredients)


                if st.button("Update Existing Row"):
                    update_existing_row(sample_id, ingredients)

            else:
                st.warning("⚠️ No text detected in image.")
        except Exception as e:
            st.error(f"❌ Error: {e}")

if __name__ == "__main__":
    if check_password():
        main()