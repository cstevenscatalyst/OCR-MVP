import streamlit as st
from google.cloud import vision
import io
import gspread
from datetime import datetime
from google.oauth2 import service_account

# === CREDENTIALS SETUP ===
vision_creds = service_account.Credentials.from_service_account_info(st.secrets["google_ocr"])
vision_client = vision.ImageAnnotatorClient(credentials=vision_creds)

sheets_creds = service_account.Credentials.from_service_account_info(st.secrets["google_sheets"])
gspread_client = gspread.authorize(sheets_creds)

sheet = gspread_client.open(SHEET_NAME).sheet1

# === Functions ===
def extract_text_from_image(image_bytes):
    image = vision.Image(content=image_bytes)
    response = vision_client.text_detection(image=image)
    if response.error.message:
        raise Exception(f"API Error: {response.error.message}")
    return response.text_annotations[0].description if response.text_annotations else None

def parse_ocr_text(ocr_text):
    sample_id = None
    ingredients = []
    capture = False
    lines = ocr_text.split('\n')

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
            ingredients.append(line.split(':', 1)[-1].strip())
            capture = True
            continue

        if capture:
            if not line.strip() or line_lower.startswith('contains'):
                capture = False
            else:
                ingredients.append(line.strip())

    return sample_id, ' '.join(ingredients).strip()

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
    
    ---
    """)

    st.image("sample_image_marked.png", caption="✅ Example of a good image", use_column_width=True)
    #st.image("sample_good_image_2.png", caption="✅ Another good example", use_column_width=True)

    uploaded_file = st.file_uploader("Upload product image (JPG, PNG)", type=["jpg", "jpeg", "png"])

    if uploaded_file:
        image_bytes = uploaded_file.read()
        try:
            ocr_text = extract_text_from_image(image_bytes)
            if ocr_text:
                # Editable text area for OCR text
                edited_text = st.text_area("🔹 Raw OCR Text (editable):", ocr_text, height=200)

                # Parse the edited text (not the original)
                sample_id, ingredients = parse_ocr_text(edited_text)

                st.success(f"✅ Sample ID: {sample_id or 'Not Found'}")
                st.success(f"✅ Ingredients: {ingredients or 'Not Found'}")

                if st.button("Add to Google Sheets"):
                    add_to_google_sheet(sample_id, ingredients)

                if st.button("Update Existing Row"):
                    update_existing_row(sample_id, ingredients)

            else:
                st.warning("⚠️ No text detected in image.")
        except Exception as e:
            st.error(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
