import streamlit as st
import openai
import os
import datetime
from google.oauth2 import id_token
from google.auth.transport import requests
from PIL import Image
import io
from google.cloud import firestore
from google.oauth2.service_account import Credentials

# --- Configurações iniciais ---

# Configura OpenAI
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Firebase Firestore setup
firebase_creds_json = st.secrets["FIREBASE_CREDENTIALS_JSON"]
credentials = Credentials.from_service_account_info(firebase_creds_json)
db = firestore.Client(credentials=credentials)

# Idiomas suportados
LANGUAGES = ['pt', 'en', 'es']

# CSS para tema preto clarinho
st.markdown("""
    <style>
    body {background-color: #121212; color: #e0e0e0;}
    .stTextInput>div>div>input {background-color: #222; color: #e0e0e0;}
    .css-1d391kg {color: #e0e0e0;}
    .css-2trqyj {background-color: #222;}
    .stButton>button {background-color: #333; color: #eee;}
    </style>
""", unsafe_allow_html=True)

# --- Funções ---

def verify_google_token(token):
    try:
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), st.secrets["GOOGLE_CLIENT_ID"])
        return idinfo['email'], idinfo['name'], idinfo['sub']
    except Exception:
        return None, None, None

def detect_language(text):
    # simplificado, você pode melhorar com biblioteca como langdetect
    if any(word in text.lower() for word in ['the', 'and', 'is']):
        return 'en'
    elif any(word in text.lower() for word in ['el', 'y', 'es']):
        return 'es'
    else:
        return 'pt'

def build_prompt(question, student_name, lang):
    greetings = {
        'pt': 'Você é a Teacher AI, uma tutora amigável que explica conteúdos escolares para estudantes do ensino fundamental e médio.',
        'en': 'You are Teacher AI, a friendly tutor who explains school content to elementary and high school students.',
        'es': 'Eres Teacher AI, una tutora amigable que explica contenidos escolares para estudiantes de primaria y secundaria.'
    }
    prompt = f"{greetings[lang]}\nO aluno se chama {student_name}.\nPergunta: {question}\nResposta:"
    return prompt

def ask_openai(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role":"user","content":prompt}],
        temperature=0.6,
        max_tokens=700
    )
    return response['choices'][0]['message']['content']

def save_chat_to_db(user_id, chat):
    doc_ref = db.collection('users').document(user_id).collection('chats').document()
    doc_ref.set({
        'timestamp': datetime.datetime.utcnow(),
        'chat': chat
    })

def load_chats_from_db(user_id):
    chats = []
    docs = db.collection('users').document(user_id).collection('chats').order_by('timestamp').stream()
    for doc in docs:
        chats.append(doc.to_dict())
    return chats

# --- Interface ---

st.title("Simple Study Ultra 📚")

# Login Google
if "login" not in st.session_state:
    token = st.text_input("Cole seu token do Google (ID Token do login OAuth2)", type="password")
    if token:
        email, name, user_id = verify_google_token(token)
        if email:
            st.session_state['login'] = True
            st.session_state['user_email'] = email
            st.session_state['user_name'] = name
            st.session_state['user_id'] = user_id
            st.success(f"Bem vindo, {name}!")
        else:
            st.error("Token inválido, tente novamente.")
else:
    st.write(f"Logado como: {st.session_state['user_email']}")

    # Input de perguntas
    question = st.text_area("Digite sua pergunta ou envie imagem/vídeo para análise")

    uploaded_file = st.file_uploader("Envie uma imagem ou vídeo", type=['png', 'jpg', 'jpeg', 'mp4', 'mov'])

    if st.button("Enviar"):

        lang = detect_language(question)

        chat_history = st.session_state.get('chat_history', [])

        # Se tem arquivo
        if uploaded_file:
            if uploaded_file.type.startswith('image/'):
                image = Image.open(uploaded_file)
                st.image(image, caption="Imagem enviada", use_column_width=True)
                # Aqui você pode colocar análise da imagem via OpenAI Vision ou outra API
                answer = "Análise da imagem ainda não implementada, mas em breve!"
            elif uploaded_file.type.startswith('video/'):
                st.video(uploaded_file)
                answer = "Análise de vídeo ainda não implementada, mas em breve!"
            else:
                answer = "Formato de arquivo não suportado."

        elif question.strip() == "":
            st.warning("Digite uma pergunta ou envie uma imagem/vídeo.")
            answer = None
        else:
            prompt = build_prompt(question, st.session_state['user_name'], lang)
            answer = ask_openai(prompt)

        if answer:
            chat_history.append({"question": question, "answer": answer})
            st.session_state['chat_history'] = chat_history
            save_chat_to_db(st.session_state['user_id'], chat_history)

        # Mostrar todo histórico
        for chat in chat_history:
            st.markdown(f"**Você:** {chat['question']}")
            st.markdown(f"**Teacher AI:** {chat['answer']}")

    # Mostrar histórico salvo no banco
    if 'chat_history' not in st.session_state:
        saved = load_chats_from_db(st.session_state['user_id'])
        st.session_state['chat_history'] = saved
