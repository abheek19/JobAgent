with open('api/main.py', 'a') as f:
    f.write('''
from fastapi import UploadFile, File
import os
import json
from google import genai

@app.post("/api/v1/resume/upload")
async def upload_resume(file: UploadFile = File(...)):
    """Uploads a PDF resume, parses it using Gemini File API, and updates master_cv_template.json"""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
        
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())
        
    try:
        settings = get_settings()
        client = genai.Client(api_key=settings.gemini_api_key)
        
        uploaded_file = client.files.upload(file=temp_path)
        
        with open("master_cv_template.json", "r") as f:
            template_schema = json.load(f)
            
        prompt = f"""
        Extract the information from this resume PDF and map it strictly into this JSON schema structure.
        Leave fields empty if the information is not present in the resume. 
        Do not add new fields outside this structure.
        
        Target Schema:
        {json.dumps(template_schema, indent=2)}
        """
        
        response = client.models.generate_content(
            model=settings.default_model_fast,
            contents=[uploaded_file, prompt],
            config={"response_mime_type": "application/json"}
        )
        
        extracted_data = json.loads(response.text)
        
        with open("master_cv_template.json", "w") as f:
            json.dump(extracted_data, f, indent=2)
            
        return {"message": "Resume successfully uploaded and parsed.", "data": extracted_data}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
''')
