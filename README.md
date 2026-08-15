# Coursera Multimodal Intelligence Platform

## Project Overview

The Coursera Multimodal Intelligence Platform is a full-stack AI-powered learning platform that allows users to access course content and interact with course material through an AI Tutor.

The platform supports multiple types of course content, including PDF documents, videos, images, and audio. It uses Retrieval-Augmented Generation (RAG) to answer questions based on the uploaded course material.

## Features

- User registration and login
- Course creation and enrollment
- PDF course material upload
- Video upload and playback
- Image upload and display
- Audio upload and playback
- Delete uploaded images and audio
- AI Tutor for course-related questions
- Course-specific AI Knowledge Base
- FAISS vector database for similarity search
- Retrieved evidence with source information
- Course-grounded AI responses

## RAG Pipeline

The AI Tutor uses Retrieval-Augmented Generation:

User Question  
↓  
Query Embedding  
↓  
FAISS Vector Search  
↓  
Relevant Course Chunks  
↓  
Retrieved Context  
↓  
LLM  
↓  
Course-Grounded Answer

The system retrieves relevant information from the selected course material before generating the response.

## Multimodal Content

The platform supports:

- PDF documents
- Videos
- Images
- Audio

Uploaded course content can be accessed from the course details page.

## AI Tutor

The AI Tutor allows students to ask questions about their course material.

For example:

**Question:**

What is Python?

The system retrieves relevant content from the Python course material and generates an answer using the retrieved evidence.

The response also displays the retrieved sources and chunks used to generate the answer.

## Technology Stack

### Frontend

- React
- Vite
- Material UI
- Axios
- React Router

### Backend

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- FAISS

### AI / RAG

- Embeddings
- FAISS Vector Database
- Retrieval-Augmented Generation (RAG)
- Large Language Model

### Media Storage

- Cloudinary

### Deployment

- GitHub
- Render

## Project Architecture

```text
                    React Frontend
                          |
                          | REST API
                          ↓
                    FastAPI Backend
                          |
             ┌────────────┼────────────┐
             ↓            ↓            ↓
         PostgreSQL   Cloudinary      RAG
                                      |
                                    FAISS
                                      |
                                     LLM
                                      |
                                      ↓
                                AI Response

[click here   to view deployed project](https://coursera-multimodal-intelligence.onrender.com)
[click here for a demo video](https://drive.google.com/file/d/1OKaXrCMACyGrISeNshMq-7o7vLH0xV_C/view?usp=sharing)
