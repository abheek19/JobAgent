with open('api/main.py', 'a') as f:
    f.write('''
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Mount the static assets directory from the built React app
dist_assets_path = os.path.join(pathlib.Path(__file__).parent.parent, "frontend", "dist", "assets")
if os.path.exists(dist_assets_path):
    app.mount("/assets", StaticFiles(directory=dist_assets_path), name="assets")

# Catch-all route to serve the React SPA
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    dist_dir = os.path.join(pathlib.Path(__file__).parent.parent, "frontend", "dist")
    file_path = os.path.join(dist_dir, full_path)
    
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    
    index_path = os.path.join(dist_dir, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
        
    return {"message": "Frontend not built yet. Run 'npm run build' in the frontend directory."}
''')
