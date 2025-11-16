# 🎤 Transcription Providers Documentation

## Overview

Audio Extraction Analysis supports multiple transcription providers with automatic failover, health checking, and circuit breaker patterns. This document provides comprehensive setup instructions, performance comparisons, and troubleshooting guides for each provider.

## Quick Comparison

| Provider | Type | Speed | Accuracy | Cost | Languages | Features | Best For |
|----------|------|-------|----------|------|-----------|----------|----------|
| **Deepgram** | Cloud | Real-time | 95%+ | $0.0125/min | 36+ | Diarization, punctuation, paragraphs | Production, streaming |
| **ElevenLabs** | Cloud | Fast | 92%+ | $0.10/min | 29 | Voice synthesis, multilingual | Content creation |
| **Whisper** | Local | 0.5-5x RT | 85-95% | Free | 100+ | Offline, privacy | Privacy, research |
| **Parakeet** | Local | 2-10x RT | 90%+ | Free | English | NVIDIA optimized | GPU acceleration |

## Provider Selection

### Automatic Selection (`--provider auto`)
The system automatically selects the best available provider:

1. **Health Check**: Tests all configured providers
2. **Priority Order**:
   - Deepgram (if API key configured)
   - ElevenLabs (if API key configured)
   - Whisper (if installed)
   - Parakeet (if installed with GPU)
3. **Fallback**: Automatically fails over to next provider on error

### Manual Selection
```bash
# Specify provider explicitly
audio-extraction-analysis process video.mp4 --provider deepgram
audio-extraction-analysis transcribe audio.mp3 --provider whisper
```

## Deepgram Provider

### Overview
Deepgram Nova 3 is a state-of-the-art cloud-based ASR service with industry-leading accuracy and real-time processing capabilities.

### Setup
```bash
# 1. Get API key from https://console.deepgram.com/
# 2. Set environment variable
export DEEPGRAM_API_KEY='your-api-key-here'

# Or use .env file
echo "DEEPGRAM_API_KEY=your-api-key" > .env
```

### Configuration
```python
# Environment variables
DEEPGRAM_API_KEY=your-key          # Required
DEEPGRAM_MODEL=nova-2              # Model version (nova, nova-2, enhanced)
DEEPGRAM_TIER=enhanced             # Tier (base, enhanced, nova)
DEEPGRAM_LANGUAGE=en               # Language code
DEEPGRAM_DIARIZE=true              # Speaker diarization
DEEPGRAM_PUNCTUATE=true            # Auto-punctuation
DEEPGRAM_PARAGRAPHS=true           # Paragraph detection
DEEPGRAM_SMART_FORMAT=true         # Smart formatting
DEEPGRAM_UTTERANCES=true           # Utterance segmentation
DEEPGRAM_DETECT_LANGUAGE=false     # Auto language detection
```

### Features
- **Speaker Diarization**: Automatic speaker identification
- **Smart Formatting**: Numbers, dates, times, currency
- **Paragraphs**: Logical paragraph breaks
- **Confidence Scores**: Per-word confidence levels
- **Profanity Filter**: Optional content filtering
- **Custom Vocabulary**: Industry-specific terms

### Pricing
- **Pay-as-you-go**: $0.0125/minute
- **Growth Plan**: $0.0043/minute (with commitment)
- **Enterprise**: Custom pricing

### Performance
- **Speed**: Real-time processing
- **Accuracy**: 95%+ on clear audio
- **Latency**: <300ms for streaming
- **File Size**: Up to 2GB
- **Duration**: No limit

### Languages Supported
English, Spanish, French, German, Italian, Portuguese, Dutch, Russian, Chinese, Japanese, Korean, Arabic, Hindi, and 20+ more.

### Best Practices
```python
# Optimal settings for meetings
DEEPGRAM_MODEL=nova-2
DEEPGRAM_DIARIZE=true
DEEPGRAM_PUNCTUATE=true
DEEPGRAM_PARAGRAPHS=true

# Optimal settings for interviews
DEEPGRAM_MODEL=enhanced
DEEPGRAM_DIARIZE=true
DEEPGRAM_UTTERANCES=true

# Optimal settings for lectures
DEEPGRAM_MODEL=nova
DEEPGRAM_PARAGRAPHS=true
DEEPGRAM_SMART_FORMAT=true
```

### Troubleshooting
```bash
# Test API key
curl https://api.deepgram.com/v1/projects \
  -H "Authorization: Token $DEEPGRAM_API_KEY"

# Check usage/balance
curl https://api.deepgram.com/v1/projects/{project_id}/usage \
  -H "Authorization: Token $DEEPGRAM_API_KEY"

# Debug mode
export LOG_LEVEL=DEBUG
audio-extraction-analysis transcribe audio.mp3 --provider deepgram
```

## ElevenLabs Provider

### Overview
ElevenLabs provides high-quality speech synthesis and transcription with advanced voice cloning capabilities.

### Setup
```bash
# 1. Get API key from https://elevenlabs.io/api
# 2. Set environment variable
export ELEVENLABS_API_KEY='your-api-key-here'

# Or use .env file
echo "ELEVENLABS_API_KEY=your-api-key" >> .env
```

### Configuration
```python
# Environment variables
ELEVENLABS_API_KEY=your-key        # Required
ELEVENLABS_MODEL=multilingual_v2   # Model version
ELEVENLABS_LANGUAGE=en             # Language code
ELEVENLABS_ENABLE_SSML=false       # SSML markup support
```

### Features
- **Voice Synthesis**: Text-to-speech with custom voices
- **Voice Cloning**: Create custom voice models
- **Multilingual**: 29 language support
- **SSML Support**: Speech Synthesis Markup Language
- **Audio Quality**: Studio-quality output

### Pricing
- **Free Tier**: 10,000 characters/month
- **Starter**: $5/month for 30,000 characters
- **Creator**: $22/month for 100,000 characters
- **Pro**: $99/month for 500,000 characters

### Performance
- **Speed**: Fast processing
- **Accuracy**: 92%+ on clear audio
- **Latency**: <500ms
- **File Size**: Up to 500MB
- **Duration**: Up to 120 minutes

### Languages Supported
English, Spanish, French, German, Italian, Portuguese, Polish, Turkish, Russian, Dutch, Swedish, Norwegian, Danish, Finnish, Greek, Czech, Croatian, Romanian, Hungarian, Bulgarian, Slovak, Slovenian, Latvian, Lithuanian, Estonian, Indonesian, Malay, Vietnamese, plus variants.

### Best Practices
```python
# Optimal settings for podcasts
ELEVENLABS_MODEL=multilingual_v2
ELEVENLABS_ENABLE_SSML=true

# Optimal settings for audiobooks
ELEVENLABS_MODEL=eleven_monolingual_v1
```

### Troubleshooting
```bash
# Test API key
curl -X GET "https://api.elevenlabs.io/v1/user" \
  -H "xi-api-key: $ELEVENLABS_API_KEY"

# Check usage
curl -X GET "https://api.elevenlabs.io/v1/user/subscription" \
  -H "xi-api-key: $ELEVENLABS_API_KEY"
```

## Whisper Provider (OpenAI)

### Overview
OpenAI's Whisper is a robust, open-source ASR model that runs locally with excellent multilingual support.

### Setup
```bash
# Install Whisper
uv add openai-whisper torch

# For GPU acceleration (recommended)
uv add openai-whisper torch torchaudio --index-url https://download.pytorch.org/whl/cu118

# Verify installation
python -c "import whisper; print('Whisper installed successfully')"
```

### Configuration
```python
# Environment variables
WHISPER_MODEL=base              # Model size (tiny, base, small, medium, large)
WHISPER_DEVICE=cuda             # Device (cuda, cpu, auto)
WHISPER_COMPUTE_TYPE=float16    # Precision (float16, float32, int8)
WHISPER_LANGUAGE=en             # Language code or 'auto'
WHISPER_TASK=transcribe         # Task (transcribe, translate)
WHISPER_TEMPERATURE=0           # Sampling temperature
WHISPER_BEAM_SIZE=5             # Beam search size
WHISPER_BEST_OF=5               # Best of N samples
WHISPER_PATIENCE=1.0            # Patience for beam search
WHISPER_NO_SPEECH_THRESHOLD=0.6 # No speech probability threshold
```

### Model Comparison

| Model | Parameters | Disk | RAM | VRAM | Speed | WER |
|-------|-----------|------|-----|------|-------|-----|
| tiny | 39M | 75MB | ~1GB | ~1GB | 32x | 10.3% |
| base | 74M | 142MB | ~1GB | ~1GB | 16x | 8.8% |
| small | 244M | 461MB | ~2GB | ~2GB | 6x | 7.0% |
| medium | 769M | 1.5GB | ~5GB | ~5GB | 2x | 5.4% |
| large | 1.5B | 2.9GB | ~10GB | ~10GB | 1x | 4.2% |

### Features
- **Offline Processing**: No internet required
- **Privacy**: Data never leaves your machine
- **Multilingual**: 100+ languages
- **Translation**: Automatic translation to English
- **Timestamps**: Word-level timestamps
- **VAD**: Voice Activity Detection

### Performance Optimization
```bash
# CPU optimization
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4

# GPU optimization
export CUDA_VISIBLE_DEVICES=0
export WHISPER_COMPUTE_TYPE=float16

# Memory optimization
export WHISPER_BEAM_SIZE=1
export WHISPER_BEST_OF=1
```

### Language Support
Supports 100+ languages including: Afrikaans, Arabic, Armenian, Azerbaijani, Belarusian, Bosnian, Bulgarian, Catalan, Chinese, Croatian, Czech, Danish, Dutch, English, Estonian, Finnish, French, Galician, German, Greek, Hebrew, Hindi, Hungarian, Icelandic, Indonesian, Italian, Japanese, Kannada, Kazakh, Korean, Latvian, Lithuanian, Macedonian, Malay, Marathi, Maori, Nepali, Norwegian, Persian, Polish, Portuguese, Romanian, Russian, Serbian, Slovak, Slovenian, Spanish, Swahili, Swedish, Tagalog, Tamil, Thai, Turkish, Ukrainian, Urdu, Vietnamese, Welsh, and more.

### Best Practices
```python
# For English content
WHISPER_MODEL=base
WHISPER_LANGUAGE=en

# For multilingual content
WHISPER_MODEL=large
WHISPER_LANGUAGE=auto

# For fast processing
WHISPER_MODEL=tiny
WHISPER_BEAM_SIZE=1

# For best accuracy
WHISPER_MODEL=large
WHISPER_BEAM_SIZE=10
```

### Troubleshooting
```bash
# Test Whisper installation
python -c "import whisper; model = whisper.load_model('tiny'); print('Model loaded')"

# Check CUDA availability
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"

# Profile performance
python -m cProfile -o whisper.prof -s cumtime \
  -c "import whisper; model = whisper.load_model('base'); model.transcribe('audio.mp3')"

# Memory issues
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512
```

## Parakeet Provider (NVIDIA NeMo)

### Overview
NVIDIA Parakeet provides GPU-accelerated ASR models optimized for high throughput and low latency.

### Setup
```bash
# Install NeMo toolkit
uv add "nemo-toolkit[asr]@1.20.0" --extra parakeet

# For specific CUDA version
uv add "nemo-toolkit[asr]@1.20.0" "torch==2.0.1+cu118" --extra parakeet --find-links https://download.pytorch.org/whl/torch_stable.html

# Verify installation
python -c "import nemo.collections.asr as nemo_asr; print('Parakeet ready')"
```

### Configuration
```python
# Environment variables
PARAKEET_MODEL=stt_en_conformer_ctc_large    # Model name
PARAKEET_DEVICE=cuda                         # Device (cuda, cpu, auto)
PARAKEET_BATCH_SIZE=8                        # Batch size
PARAKEET_BEAM_SIZE=10                        # Beam search size
PARAKEET_USE_FP16=true                       # Half precision
PARAKEET_CHUNK_LENGTH=30                     # Audio chunk seconds
PARAKEET_MODEL_CACHE_DIR=~/.cache/parakeet   # Model cache location
PARAKEET_NUM_WORKERS=4                       # Parallel workers
```

### Available Models

| Model | Architecture | Accuracy | Speed | Memory | Use Case |
|-------|-------------|----------|-------|--------|----------|
| stt_en_conformer_ctc_large | CTC | High | Fast | 4GB | General |
| stt_en_conformer_transducer_large | RNN-T | Highest | Medium | 6GB | Streaming |
| stt_en_fastconformer_ctc_large | CTC | Medium | Fastest | 2GB | Real-time |
| stt_en_squeezeformer_ctc_large | CTC | High | Fast | 3GB | Edge |

### Features
- **GPU Acceleration**: NVIDIA CUDA optimized
- **TensorRT**: Production inference optimization
- **Streaming**: Real-time transcription
- **Custom Models**: Fine-tuning support
- **Noise Robustness**: Pre-trained on noisy data
- **Multi-GPU**: Distributed processing

### Performance
- **Speed**: 2-10x real-time on GPU
- **Accuracy**: 90%+ WER
- **Latency**: <100ms streaming
- **Throughput**: 100+ hours/hour on A100
- **Batch Processing**: Efficient batching

### GPU Requirements
- **Minimum**: GTX 1060 (6GB VRAM)
- **Recommended**: RTX 3060 (12GB VRAM)
- **Optimal**: A100/H100 (40GB+ VRAM)
- **CUDA**: 11.8+
- **Driver**: 515+

### Best Practices
```python
# For accuracy
PARAKEET_MODEL=stt_en_conformer_transducer_large
PARAKEET_BEAM_SIZE=20

# For speed
PARAKEET_MODEL=stt_en_fastconformer_ctc_large
PARAKEET_USE_FP16=true
PARAKEET_BATCH_SIZE=16

# For streaming
PARAKEET_MODEL=stt_en_conformer_transducer_large
PARAKEET_CHUNK_LENGTH=10
```

### Troubleshooting
```bash
# Check GPU availability
nvidia-smi

# Test model loading
python -c "from nemo.collections.asr import models; \
  model = models.EncDecCTCModel.from_pretrained('stt_en_conformer_ctc_small'); \
  print('Model loaded')"

# Memory issues
export CUDA_VISIBLE_DEVICES=0
export TF_FORCE_GPU_ALLOW_GROWTH=true

# Profile performance
nsys profile python -m src.cli transcribe audio.mp3 --provider parakeet
```

## Provider Health Checking

### Automatic Health Checks
The system automatically checks provider health:

```python
from src.providers.factory import TranscriptionProviderFactory

# Check all providers
health_status = TranscriptionProviderFactory.check_all_provider_health()
print(health_status)
# {'deepgram': 'healthy', 'whisper': 'not_installed', ...}

# Check specific provider
is_healthy = TranscriptionProviderFactory.check_provider_health('deepgram')
```

### Manual Health Check
```bash
# Check provider health via CLI
audio-extraction-analysis check-health

# Output:
# Provider Health Status:
# ✅ Deepgram: Healthy (API key valid, quota available)
# ❌ ElevenLabs: API key not configured
# ✅ Whisper: Healthy (base model available)
# ⚠️  Parakeet: Not installed
```

### Health Check Criteria

#### Deepgram
- API key configured
- API key valid (test request)
- Quota/credits available
- Network connectivity

#### ElevenLabs
- API key configured
- API key valid
- Character quota available
- Service accessible

#### Whisper
- Package installed
- Model downloaded
- Sufficient memory
- CUDA available (if configured)

#### Parakeet
- NeMo installed
- Model downloaded
- GPU available
- CUDA version compatible

## Circuit Breaker Pattern

### Overview
All providers implement circuit breaker pattern for fault tolerance:

```python
# Circuit breaker states
CLOSED = "closed"      # Normal operation
OPEN = "open"          # Failing, reject requests
HALF_OPEN = "half_open"  # Testing recovery

# Configuration
FAILURE_THRESHOLD = 5   # Failures before opening
RECOVERY_TIMEOUT = 60    # Seconds before retry
SUCCESS_THRESHOLD = 2    # Successes to close
```

### Behavior
1. **Closed State**: Normal operation, requests processed
2. **Open State**: After 5 failures, reject requests for 60s
3. **Half-Open State**: Allow test request after timeout
4. **Recovery**: After 2 successes, return to closed state

### Manual Reset
```python
from src.providers.factory import TranscriptionProviderFactory

# Reset circuit breaker for provider
provider = TranscriptionProviderFactory.create_provider('deepgram')
provider.reset_circuit_breaker()
```

## Provider Selection Strategy

### Priority Order
```python
PROVIDER_PRIORITY = [
    'deepgram',     # Best accuracy, real-time
    'elevenlabs',   # Good accuracy, fast
    'whisper',      # Good accuracy, private
    'parakeet'      # Fast, GPU required
]
```

### Selection Factors
1. **Availability**: Provider installed/configured
2. **Health**: Provider responding correctly
3. **Performance**: Speed requirements
4. **Cost**: Budget constraints
5. **Privacy**: Data sensitivity
6. **Language**: Language support

### Custom Strategy
```python
# Custom provider selection
def select_provider(criteria):
    if criteria['privacy_required']:
        return 'whisper'
    elif criteria['real_time']:
        return 'deepgram'
    elif criteria['gpu_available']:
        return 'parakeet'
    else:
        return 'auto'
```

## Performance Benchmarks

### Test Setup
- **Audio**: 60-minute meeting recording
- **Quality**: 44.1kHz, stereo
- **Content**: Multiple speakers, technical discussion
- **Hardware**: Intel i7-10700K, RTX 3080, 32GB RAM

### Results

| Provider | Time | Accuracy | Memory | Cost |
|----------|------|----------|--------|------|
| Deepgram Nova | 45s | 95.2% | 500MB | $0.75 |
| ElevenLabs | 120s | 92.1% | 800MB | $6.00 |
| Whisper Large | 600s | 94.8% | 10GB | $0.00 |
| Whisper Base | 180s | 88.3% | 2GB | $0.00 |
| Parakeet CTC | 90s | 91.5% | 4GB | $0.00 |
| Parakeet RNN-T | 150s | 93.2% | 6GB | $0.00 |

## Cost Optimization

### Strategies
1. **Use Whisper/Parakeet for bulk processing**: Free, good accuracy
2. **Deepgram for real-time/critical**: Best accuracy, reasonable cost
3. **ElevenLabs for special features**: Voice synthesis, SSML
4. **Batch processing**: Reduce API calls
5. **Caching**: Store and reuse transcripts

### Cost Calculator
```python
def calculate_cost(duration_minutes, provider='auto'):
    costs = {
        'deepgram': 0.0125,      # per minute
        'elevenlabs': 0.10,      # per minute
        'whisper': 0.0,          # free
        'parakeet': 0.0          # free
    }
    
    return duration_minutes * costs.get(provider, 0)

# Example: 2-hour meeting
cost = calculate_cost(120, 'deepgram')  # $1.50
```

## Migration Guide

### From Cloud to Local
```bash
# Step 1: Install local provider
uv add openai-whisper torch

# Step 2: Download model
python -c "import whisper; whisper.load_model('base')"

# Step 3: Update configuration
export TRANSCRIPTION_PROVIDER=whisper

# Step 4: Test
audio-extraction-analysis transcribe test.mp3 --provider whisper
```

### From Local to Cloud
```bash
# Step 1: Get API key
# Visit https://console.deepgram.com/

# Step 2: Configure
export DEEPGRAM_API_KEY='your-key'

# Step 3: Test
audio-extraction-analysis transcribe test.mp3 --provider deepgram
```

## Troubleshooting Common Issues

### "No providers available"
```bash
# Check installation
uv pip list | grep -E "deepgram|whisper|nemo"

# Install at least one provider
uv add openai-whisper

# Verify
audio-extraction-analysis check-health
```

### "API key invalid"
```bash
# Check environment
env | grep -E "DEEPGRAM|ELEVENLABS"

# Test API key
curl https://api.deepgram.com/v1/projects \
  -H "Authorization: Token $DEEPGRAM_API_KEY"

# Use .env file
echo "DEEPGRAM_API_KEY=your-key" > .env
```

### "Out of memory"
```bash
# Use smaller model
export WHISPER_MODEL=tiny

# Reduce batch size
export PARAKEET_BATCH_SIZE=1

# Use CPU instead
export WHISPER_DEVICE=cpu
```

### "Slow processing"
```bash
# Use GPU
export WHISPER_DEVICE=cuda

# Use faster model
export WHISPER_MODEL=tiny

# Use cloud provider
export TRANSCRIPTION_PROVIDER=deepgram
```

## Best Practices

### Development
1. Use Whisper tiny/base for rapid iteration
2. Mock providers for testing
3. Cache transcripts to avoid re-processing
4. Use --verbose for debugging

### Production
1. Use Deepgram for reliability
2. Implement retry with exponential backoff
3. Monitor provider health
4. Set up alerts for failures
5. Implement fallback providers
6. Use circuit breakers
7. Log all provider switches

### Security
1. Never commit API keys
2. Use environment variables or secrets management
3. Rotate API keys regularly
4. Monitor API usage for anomalies
5. Use local providers for sensitive data

---

*Last Updated: November 2024*
*Provider Versions: Deepgram v4.8, ElevenLabs v1.0, Whisper v20231117, Parakeet v1.20*
