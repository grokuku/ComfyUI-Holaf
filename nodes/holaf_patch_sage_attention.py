# Licence to be added if the project has one.

from comfy.ldm.modules import attention as comfy_attention
import comfy.model_patcher
import comfy.utils
import comfy.sd
import torch
from typing import Optional, Tuple
from comfy.patcher_extension import CallbacksMP

# This node has an external dependency on the 'sageattention' library.
# It was not found in the source files and must be installed in your environment.
# You can likely install it from https://github.com/thu-ml/SageAttention
try:
    from sageattention import sageattn, sageattn_qk_int8_pv_fp16_cuda, sageattn_qk_int8_pv_fp16_triton, sageattn_qk_int8_pv_fp8_cuda
except ImportError:
    print("***********************************************************************************")
    print("Warning: Holaf-Nodes - 'sageattention' library not found.")
    print("The 'Patch Sage Attention (Holaf)' node will not work.")
    print("Please install it, for example via: pip install sage-attention")
    print("***********************************************************************************")


sageattn_modes = ["disabled", "auto", "sageattn_qk_int8_pv_fp16_cuda", "sageattn_qk_int8_pv_fp16_triton", "sageattn_qk_int8_pv_fp8_cuda", "sageattn_qk_int8_pv_fp8_cuda++"]

_initialized = False
_original_functions = {}

if not _initialized:
    _original_functions["orig_attention"] = comfy_attention.optimized_attention
    try:
        _original_functions["original_qwen_forward"] = comfy.ldm.qwen_image.model.Attention.forward
    except:
        pass
    _initialized = True

class HolafSageAttentionPatcher:
    """
    This class is a container for the patching logic, adapted from the original file.
    It's not a node itself but holds the core functionality.
    """
    @torch.compiler.disable()
    def _patch_modules(self, sage_attention):
        try:
            from comfy.ldm.qwen_image.model import apply_rotary_emb
            def qwen_sage_forward(
                self,
                hidden_states: torch.FloatTensor,  # Image stream
                encoder_hidden_states: torch.FloatTensor = None,  # Text stream
                encoder_hidden_states_mask: torch.FloatTensor = None,
                attention_mask: Optional[torch.FloatTensor] = None,
                image_rotary_emb: Optional[torch.Tensor] = None,
            ) -> Tuple[torch.Tensor, torch.Tensor]:
                seq_txt = encoder_hidden_states.shape[1]

                img_query = self.to_q(hidden_states).unflatten(-1, (self.heads, -1))
                img_key = self.to_k(hidden_states).unflatten(-1, (self.heads, -1))
                img_value = self.to_v(hidden_states).unflatten(-1, (self.heads, -1))

                txt_query = self.add_q_proj(encoder_hidden_states).unflatten(-1, (self.heads, -1))
                txt_key = self.add_k_proj(encoder_hidden_states).unflatten(-1, (self.heads, -1))
                txt_value = self.add_v_proj(encoder_hidden_states).unflatten(-1, (self.heads, -1))

                img_query = self.norm_q(img_query)
                img_key = self.norm_k(img_key)
                txt_query = self.norm_added_q(txt_query)
                txt_key = self.norm_added_k(txt_key)

                joint_query = torch.cat([txt_query, img_query], dim=1)
                joint_key = torch.cat([txt_key, img_key], dim=1)
                joint_value = torch.cat([txt_value, img_value], dim=1)

                joint_query = apply_rotary_emb(joint_query, image_rotary_emb)
                joint_key = apply_rotary_emb(joint_key, image_rotary_emb)

                joint_query = joint_query.flatten(start_dim=2)
                joint_key = joint_key.flatten(start_dim=2)
                joint_value = joint_value.flatten(start_dim=2)

                joint_hidden_states = attention_sage(joint_query, joint_key, joint_value, self.heads, attention_mask)

                txt_attn_output = joint_hidden_states[:, :seq_txt, :]
                img_attn_output = joint_hidden_states[:, seq_txt:, :]

                img_attn_output = self.to_out[0](img_attn_output)
                img_attn_output = self.to_out[1](img_attn_output)
                txt_attn_output = self.to_add_out(txt_attn_output)

                return img_attn_output, txt_attn_output
        except:
            print("Failed to patch QwenImage attention, Comfy not updated, skipping")

        if sage_attention != "disabled":
            print("Patching comfy attention to use sageattn")

            def set_sage_func(sage_attention):
                if sage_attention == "auto":
                    def func(q, k, v, is_causal=False, attn_mask=None, tensor_layout="NHD"):
                        return sageattn(q, k, v, is_causal=is_causal, attn_mask=attn_mask, tensor_layout=tensor_layout)
                    return func
                elif sage_attention == "sageattn_qk_int8_pv_fp16_cuda":
                    def func(q, k, v, is_causal=False, attn_mask=None, tensor_layout="NHD"):
                        return sageattn_qk_int8_pv_fp16_cuda(q, k, v, is_causal=is_causal, attn_mask=attn_mask, pv_accum_dtype="fp32", tensor_layout=tensor_layout)
                    return func
                elif sage_attention == "sageattn_qk_int8_pv_fp16_triton":
                    def func(q, k, v, is_causal=False, attn_mask=None, tensor_layout="NHD"):
                        return sageattn_qk_int8_pv_fp16_triton(q, k, v, is_causal=is_causal, attn_mask=attn_mask, tensor_layout=tensor_layout)
                    return func
                elif sage_attention == "sageattn_qk_int8_pv_fp8_cuda":
                    def func(q, k, v, is_causal=False, attn_mask=None, tensor_layout="NHD"):
                        return sageattn_qk_int8_pv_fp8_cuda(q, k, v, is_causal=is_causal, attn_mask=attn_mask, pv_accum_dtype="fp32+fp32", tensor_layout=tensor_layout)
                    return func
                elif sage_attention == "sageattn_qk_int8_pv_fp8_cuda++":
                    def func(q, k, v, is_causal=False, attn_mask=None, tensor_layout="NHD"):
                        return sageattn_qk_int8_pv_fp8_cuda(q, k, v, is_causal=is_causal, attn_mask=attn_mask, pv_accum_dtype="fp32+fp16", tensor_layout=tensor_layout)
                    return func

            sage_func = set_sage_func(sage_attention)

            @torch.compiler.disable()
            def attention_sage(q, k, v, heads, mask=None, attn_precision=None, skip_reshape=False, skip_output_reshape=False):
                if skip_reshape:
                    b, _, _, dim_head = q.shape
                    tensor_layout="HND"
                else:
                    b, _, dim_head = q.shape
                    dim_head //= heads
                    q, k, v = map(
                        lambda t: t.view(b, -1, heads, dim_head),
                        (q, k, v),
                    )
                    tensor_layout="NHD"
                if mask is not None:
                    if mask.ndim == 2:
                        mask = mask.unsqueeze(0)
                    if mask.ndim == 3:
                        mask = mask.unsqueeze(1)
                out = sage_func(q, k, v, attn_mask=mask, is_causal=False, tensor_layout=tensor_layout)
                if tensor_layout == "HND":
                    if not skip_output_reshape:
                        out = (
                            out.transpose(1, 2).reshape(b, -1, heads * dim_head)
                        )
                else:
                    if skip_output_reshape:
                        out = out.transpose(1, 2)
                    else:
                        out = out.reshape(b, -1, heads * dim_head)
                return out

            comfy_attention.optimized_attention = attention_sage
            comfy.ldm.hunyuan_video.model.optimized_attention = attention_sage
            comfy.ldm.flux.math.optimized_attention = attention_sage
            comfy.ldm.genmo.joint_model.asymm_models_joint.optimized_attention = attention_sage
            comfy.ldm.cosmos.blocks.optimized_attention = attention_sage
            comfy.ldm.wan.model.optimized_attention = attention_sage
            try:
                comfy.ldm.qwen_image.model.Attention.forward = qwen_sage_forward
            except:
                pass

        else:
            print("Restoring initial comfy attention")
            comfy_attention.optimized_attention = _original_functions.get("orig_attention")
            comfy.ldm.hunyuan_video.model.optimized_attention = _original_functions.get("orig_attention")
            comfy.ldm.flux.math.optimized_attention = _original_functions.get("orig_attention")
            comfy.ldm.genmo.joint_model.asymm_models_joint.optimized_attention = _original_functions.get("orig_attention")
            comfy.ldm.cosmos.blocks.optimized_attention = _original_functions.get("orig_attention")
            comfy.ldm.wan.model.optimized_attention = _original_functions.get("orig_attention")
            try:
                comfy.ldm.qwen_image.model.Attention.forward = _original_functions.get("original_qwen_forward")
            except:
                pass

class HolafPatchSageAttention(HolafSageAttentionPatcher):
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "model": ("MODEL",),
            "sage_attention": (sageattn_modes, {"default": "auto"}),
        }}

    RETURN_TYPES = ("MODEL", )
    FUNCTION = "patch"
    CATEGORY = "Holaf/experimental"

    def patch(self, model, sage_attention):
        model_clone = model.clone()
        
        @torch.compiler.disable()
        def patch_attention_enable(model):
            self._patch_modules(sage_attention)
        
        @torch.compiler.disable()
        def patch_attention_disable(model):
            self._patch_modules("disabled")
        
        model_clone.add_callback(CallbacksMP.ON_PRE_RUN, patch_attention_enable)
        model_clone.add_callback(CallbacksMP.ON_CLEANUP, patch_attention_disable)
        
        return (model_clone,)

NODE_CLASS_MAPPINGS = {
    "HolafPatchSageAttention": HolafPatchSageAttention
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "HolafPatchSageAttention": "Patch Sage Attention (Holaf)"
}
