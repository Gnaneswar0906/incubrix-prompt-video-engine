import os
import sys

# Ensure repository root is in python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Set default single-container environment variables
os.environ.setdefault("QUEUE_BACKEND", "inprocess")
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/incubrix.db")

from service.app import app

try:
    import gradio as gr

    # Create a clean Gradio interface embedding the IncuBrix Web Studio
    with gr.Blocks(title="IncuBrix Prompt-Based Video Editing Studio", theme=gr.themes.Base()) as demo:
        gr.HTML("""
        <div style="text-align: center; padding: 12px 0; background: #0f172a; color: white; border-radius: 8px; margin-bottom: 12px;">
            <h2 style="margin: 0; font-family: system-ui, sans-serif; font-size: 24px; color: #38bdf8;">IncuBrix Prompt-Based Video Editing Studio</h2>
            <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 14px;">Deterministic, Content-Anchored AI Video Editing Engine</p>
        </div>
        """)
        
        with gr.Tabs():
            with gr.TabItem("Interactive Web Studio"):
                gr.HTML("""
                <iframe src="/index.html" width="100%" height="900px" style="border: 1px solid #334155; border-radius: 8px; background: #0b0f19;"></iframe>
                """)
            with gr.TabItem("API Documentation (Swagger UI)"):
                gr.HTML("""
                <iframe src="/docs" width="100%" height="900px" style="border: 1px solid #334155; border-radius: 8px; background: white;"></iframe>
                """)

    # Mount the FastAPI service onto Gradio
    app = gr.mount_gradio_app(app, demo, path="/")
except ImportError:
    demo = None

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    if demo:
        demo.launch(server_name="0.0.0.0", server_port=port)
    else:
        uvicorn.run(app, host="0.0.0.0", port=port)
