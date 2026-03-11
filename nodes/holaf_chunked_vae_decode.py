import torch
import nodes
import inspect

class HolafChunkedVAEDecode:
    """
    Advanced VRAM-saving VAE Decoder with built-in Benchmarking (Auto-Tune).
    Combines spatial tiling, temporal chunking, and Contextual Hard-Cut assembly.
    Supports both 4D (Standard/SVD) and 5D (LTX-Video) latent tensors.
    """
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "samples": ("LATENT", ),
                "vae": ("VAE", ),
                "bench_mode": ("BOOLEAN", {"default": False, "label_on": "ON (Test Limits)", "label_off": "OFF (Normal Decode)"}),
                "chunk_size": ("INT", {"default": 8, "min": 1, "max": 4096, "step": 1, "tooltip": "Used when Bench Mode is OFF."}),
                "chunk_overlap": ("INT", {"default": 2, "min": 0, "max": 128, "step": 1, "tooltip": "Context frames. Higher = better continuity, but slightly slower."}),
                "tile_size": ("INT", {"default": 512, "min": 256, "max": 4096, "step": 64}),
                "spatial_overlap": ("INT", {"default": 64, "min": 0, "max": 1024, "step": 8}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "process"
    CATEGORY = "Holaf/Video"

    def process(self, samples, vae, bench_mode, chunk_size, chunk_overlap, tile_size, spatial_overlap):
        latent_tensor = samples["samples"]
        
        if bench_mode:
            return self.run_benchmark(latent_tensor, vae, spatial_overlap)
        else:
            return self.run_decode(latent_tensor, vae, chunk_size, chunk_overlap, tile_size, spatial_overlap)

    def run_benchmark(self, latent_tensor, vae, spatial_overlap):
        is_5d = latent_tensor.ndim == 5
        total_latents = latent_tensor.shape[2] if is_5d else latent_tensor.shape[0]

        print("\n" + "="*50)
        print("🚀 HOLAF VAE BENCHMARK INITIATED")
        print("="*50)
        print(f"Testing with REAL latent of shape: {latent_tensor.shape}")
        print(f"Detected Temporal Dimension: {total_latents} latents (5D: {is_5d})")
        
        tile_sizes_to_test = [1024, 768, 512, 384, 256]
        test_chunks = [1, 2, 4, 8, 12, 16, 24, 32, 48, 64]
        
        results = {}
        native_tiled_decoder = nodes.VAEDecodeTiled()
        sig = inspect.signature(native_tiled_decoder.decode)

        for t_size in tile_sizes_to_test:
            print(f"\n▶ Testing Tile Size: {t_size}x{t_size}...")
            max_stable_chunk = 0
            
            for c_size in test_chunks:
                if c_size > total_latents:
                    c_size = total_latents
                    
                print(f"  ├─ Trying chunk_size = {c_size}...", end=" ")
                
                try:
                    if is_5d:
                        chunk_latent = latent_tensor[:, :, :c_size, :, :]
                    else:
                        chunk_latent = latent_tensor[:c_size]
                    
                    kwargs = {
                        "vae": vae,
                        "samples": {"samples": chunk_latent},
                        "tile_size": t_size
                    }
                    
                    if "overlap" in sig.parameters: kwargs["overlap"] = spatial_overlap
                    if "temporal_size" in sig.parameters: kwargs["temporal_size"] = 4096
                    if "temporal_overlap" in sig.parameters: kwargs["temporal_overlap"] = 0

                    _ = native_tiled_decoder.decode(**kwargs)
                    
                    print("✅ PASS")
                    max_stable_chunk = c_size
                    
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        
                    if c_size == total_latents:
                        break

                except RuntimeError as e:
                    if "memory" in str(e).lower() or "oom" in str(e).lower():
                        print("❌ OOM (Out of Memory)")
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                        break 
                    else:
                        raise e 

            results[t_size] = max_stable_chunk

        print("\n" + "="*50)
        print("📊 BENCHMARK RESULTS SUMMARY")
        print("="*50)
        for t, c in results.items():
            if c == 0:
                print(f"❌ Tile {t}: FAILED even at chunk 1. (Tile too large)")
            else:
                print(f"✅ Tile {t}: Set chunk_size to {c} (or slightly lower)")
        print("="*50 + "\n")

        dummy_image = torch.zeros((1, 64, 64, 3), dtype=torch.float32, device="cpu")
        return (dummy_image,)

    def run_decode(self, latent_tensor, vae, chunk_size, chunk_overlap, tile_size, spatial_overlap):
        is_5d = latent_tensor.ndim == 5
        total_latents = latent_tensor.shape[2] if is_5d else latent_tensor.shape[0]
        
        chunk_overlap = min(chunk_overlap, chunk_size - 1)
        
        native_tiled_decoder = nodes.VAEDecodeTiled()
        sig = inspect.signature(native_tiled_decoder.decode)
        decoded_chunks = []
        
        step = chunk_size - chunk_overlap
        if step <= 0: step = 1
            
        for i in range(0, total_latents, step):
            end_idx = min(i + chunk_size, total_latents)
            
            if is_5d:
                chunk_latent = latent_tensor[:, :, i:end_idx, :, :]
            else:
                chunk_latent = latent_tensor[i:end_idx]
            
            kwargs = {
                "vae": vae,
                "samples": {"samples": chunk_latent},
                "tile_size": tile_size
            }
            if "overlap" in sig.parameters: kwargs["overlap"] = spatial_overlap
            if "temporal_size" in sig.parameters: kwargs["temporal_size"] = 4096
            if "temporal_overlap" in sig.parameters: kwargs["temporal_overlap"] = 0

            (decoded_image, ) = native_tiled_decoder.decode(**kwargs)
            
            latent_temporal_size = chunk_latent.shape[2] if is_5d else chunk_latent.shape[0]
            compression_ratio = decoded_image.shape[0] / latent_temporal_size
            
            decoded_chunks.append({
                "image": decoded_image.cpu(), 
                "ratio": compression_ratio
            })
            
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                
            if end_idx >= total_latents:
                break
                
        # --- CPU Contextual Hard-Cut Assembly ---
        if not decoded_chunks: 
            return (torch.empty(0), )
            
        trimmed_chunks = []
        num_chunks = len(decoded_chunks)

        for i in range(num_chunks):
            chunk_img = decoded_chunks[i]["image"]
            ratio = decoded_chunks[i]["ratio"]
            
            # Distribute the overlap dropping: half from the end of prev, half from start of next.
            drop_latents_back = chunk_overlap // 2
            drop_latents_front = chunk_overlap - drop_latents_back
            
            # Convert latents to image frames based on the VAE compression ratio
            drop_frames_front = int(drop_latents_front * ratio) if i > 0 else 0
            drop_frames_back = int(drop_latents_back * ratio) if i < num_chunks - 1 else 0
            
            start_idx = drop_frames_front
            end_idx = chunk_img.shape[0] - drop_frames_back
            
            # Keep only the highly confident "core" of the chunk
            valid_part = chunk_img[start_idx:end_idx]
            trimmed_chunks.append(valid_part)
            
        final_video = torch.cat(trimmed_chunks, dim=0)
        return (final_video, )