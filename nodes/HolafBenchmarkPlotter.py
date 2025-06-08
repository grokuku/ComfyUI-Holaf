import torch
import numpy as np
import io
from PIL import Image, ImageOps

# --- Dependency Check ---
# This node requires external libraries. It will be disabled if they are not found.
try:
    import pandas as pd
    _pandas_available = True
except ImportError:
    _pandas_available = False
    print("[HolafBenchmarkPlotter] Warning: 'pandas' not found. This node is disabled. `pip install pandas`")
try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg') # Use a non-interactive backend for server environments.
    _matplotlib_available = True
except ImportError:
    _matplotlib_available = False
    print("[HolafBenchmarkPlotter] Warning: 'matplotlib' not found. This node is disabled. `pip install matplotlib`")

class HolafBenchmarkPlotter:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                # The CSV-formatted text from the Benchmark Runner.
                "report_text": ("STRING", {"default": "", "multiline": True}),
            },
            "optional": {
                 "plot_title": ("STRING", {"default": "Benchmark: Pixels/s vs Resolution"}),
            }
        }

    RETURN_TYPES = ("IMAGE", "IMAGE",)
    RETURN_NAMES = ("plot_image_light", "plot_image_dark",)
    FUNCTION = "plot_benchmark"
    CATEGORY = "Holaf"

    def plot_to_tensor(self, fig):
        """Helper to convert a Matplotlib figure into a ComfyUI image tensor."""
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        image = Image.open(buf).convert("RGB")
        image_np = np.array(image).astype(np.float32) / 255.0
        image_tensor = torch.from_numpy(image_np)[None,]
        plt.close(fig) # Essential for releasing memory.
        return image_tensor

    def _create_plot(self, df, plot_title, style_context=None, text_color='black', grid_color='lightgray'):
        """A reusable helper function to generate a plot with a specific theme."""
        if style_context: plt.style.use(style_context)
        
        fig, ax = plt.subplots(figsize=(12, 7))

        # Group data by model name to plot each as a separate, labeled curve.
        if 'Model Name' in df.columns:
            for name, group in df.groupby('Model Name'):
                ax.plot(group['ResValue'], group['PixelsPerSec'], marker='o', linestyle='-', label=name)
            ax.legend(loc='best', fontsize='small')
        else:
            ax.plot(df['ResValue'], df['PixelsPerSec'], marker='o', linestyle='-')

        # Style the plot elements.
        ax.set_xlabel("Resolution (Width in Pixels)", color=text_color)
        ax.set_ylabel("Performance (Pixels per Second)", color=text_color)
        ax.set_title(plot_title, color=text_color)
        ax.grid(True, which='both', linestyle='--', linewidth=0.5, color=grid_color)
        ax.tick_params(colors=text_color)
        for spine in ax.spines.values():
            spine.set_edgecolor(text_color)

        # Extract system info from the DataFrame and add it as text below the plot.
        system_info_cols = ["GPU", "GPU Memory (GB)", "CPU", "RAM (GB)", "OS"]
        info_text = " | ".join(f"{col}: {df.iloc[0][col]}" for col in system_info_cols if col in df.columns)
        if info_text:
            plt.figtext(0.5, 0.01, info_text, ha="center", fontsize=8, color=text_color)
            plt.subplots_adjust(bottom=0.2)
        
        return self.plot_to_tensor(fig)

    def plot_benchmark(self, report_text, plot_title="Benchmark: Pixels/s vs Resolution"):
        if not _pandas_available or not _matplotlib_available:
            return (torch.zeros([1, 64, 64, 3]), torch.zeros([1, 64, 64, 3]))
        if not report_text or not report_text.strip():
            return (torch.zeros([1, 64, 64, 3]), torch.zeros([1, 64, 64, 3]))

        try:
            # --- Data Parsing and Preparation ---
            # Read the CSV text directly into a pandas DataFrame without creating a file.
            df = pd.read_csv(io.StringIO(report_text))
            
            # Prepare data for plotting: create a numeric resolution value and convert pixels/s.
            df['ResValue'] = df['Resolution'].astype(str).str.split('x', expand=True)[0].astype(int)
            df['PixelsPerSec'] = pd.to_numeric(df['Pixels/s'], errors='coerce')
            df.dropna(subset=['ResValue', 'PixelsPerSec'], inplace=True)
            df = df.sort_values(by='ResValue')
            if df.empty: raise ValueError("No valid numeric data found in CSV.")

            # --- Plot Generation ---
            # Generate both light and dark theme plots using the reusable helper.
            plot_light = self._create_plot(df.copy(), plot_title, style_context='default', text_color='black', grid_color='lightgray')
            plot_dark = self._create_plot(df.copy(), plot_title, style_context='dark_background', text_color='white', grid_color='gray')

            return (plot_light, plot_dark)
        except Exception as e:
            print(f"[HolafBenchmarkPlotter] Error generating plot: {e}")
            traceback.print_exc()
            return (torch.zeros([1, 64, 64, 3]), torch.zeros([1, 64, 64, 3]))