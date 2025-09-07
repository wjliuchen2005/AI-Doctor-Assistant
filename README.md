# AI Doctor Assistant

An intelligent medical consultation system with voice interaction capabilities, built with PyQt5 and integrated with AI language models.

## 📋 Overview

AI Doctor Assistant is a desktop application designed to facilitate medical consultations through natural language processing and voice interaction. The system conducts structured medical interviews, collects patient information, and generates comprehensive electronic medical records (EMR).

### Key Features

- 🎤 **Voice Input/Output**: Real-time speech recognition and text-to-speech synthesis using Baidu AI services
- 💬 **Interactive Chat Interface**: WeChat-style chat bubbles for intuitive doctor-patient communication
- 📝 **Automated EMR Generation**: Structured medical records generated using DeepSeek API
- 🔊 **Multi-language Support**: Currently supports Mandarin Chinese
- 💾 **Local Record Storage**: All consultation records saved locally for privacy and accessibility

## 🏗️ Architecture

The application utilizes:
- **PyQt5** for the graphical user interface
- **Baidu Speech API** for voice recognition and synthesis
- **DeepSeek API** for intelligent response generation
- **Pygame** for audio playback functionality

## 📚 Academic Background

The prompt engineering methodology used in this project is based on the research paper:

> **"Evaluation and practical application of prompt-driven ChatGPTs for EMR generation"**  
> Nature Digital Medicine, 2025  
> DOI: [10.1038/s41746-025-01472-x](https://doi.org/10.1038/s41746-025-01472-x)

Specifically, this implementation utilizes **Prompt 5** from the paper, which has been optimized for structured medical history collection.

## 🚀 Quick Start

### Option 1: Using Pre-built Executables

Download the latest release for your platform:

- **Windows**: [AI_Doctor_Assistant_v1.0_win64.exe](releases/windows/)

### Option 2: Running from Source

Disclaimer: This software is for educational and research purposes. Always consult qualified healthcare professionals for medical advice.
