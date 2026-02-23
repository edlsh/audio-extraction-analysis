from typing import Any, Optional, Union, List, Dict

class Whisper:
    def transcribe(
        self,
        audio: Union[str, Any],
        verbose: Optional[bool] = None,
        temperature: Union[float, List[float], None] = None,
        compression_ratio_threshold: Optional[float] = None,
        logprob_threshold: Optional[float] = None,
        no_speech_threshold: Optional[float] = None,
        condition_on_previous_text: Optional[bool] = None,
        initial_prompt: Optional[str] = None,
        word_timestamps: bool = False,
        prepend_punctuations: str = "\"'“¿([{-",
        append_punctuations: str = "\"'.。,，!！?？:：”)]}、",
        fp16: Optional[bool] = None,
        **kwargs: Any
    ) -> Dict[str, Any]: ...
    
    @property
    def device(self) -> Any: ...
    @property
    def dims(self) -> Any: ...

def load_model(
    name: str,
    device: Optional[Union[str, Any]] = None,
    download_root: Optional[str] = None,
    in_memory: bool = False,
) -> Whisper: ...

class DecodingOptions:
    def __init__(self, **kwargs: Any) -> None: ...

def pad_or_trim(array: Any, length: int = 3000) -> Any: ...
def log_mel_spectrogram(audio: Any, n_mels: int = 80) -> Any: ...
def decode(model: Whisper, mel: Any, options: DecodingOptions) -> Any: ...
def detect_language(model: Whisper, mel: Any) -> Any: ...
