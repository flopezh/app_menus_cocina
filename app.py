# -*- coding: utf-8 -*-
"""
Created on Sat Nov 29 09:47:14 2025

@author: Administrator
"""

import os
import uuid
from flask import Flask, session, redirect, url_for, request, render_template
import msal
import requests

app = Flask(__name__)
app.secret_key = str(uuid.uuid4())  # Necesario para sesiones

# Configuración de Azure AD
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
TENANT_ID = os.environ.get("TENANT_ID")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
REDIRECT_PATH = "/getAToken"
SCOPE = ["User.Read", "Mail.Send"]
REDIRECT_URI = f"http://localhost:5000{REDIRECT_PATH}"

def build_msal_app(cache=None):
    return msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        client_credential=CLIENT_SECRET,
        token_cache=cache
    )

def get_token_from_cache():
    cache = msal.SerializableTokenCache()
    if session.get("token_cache"):
        cache.deserialize(session["token_cache"])
    cca = build_msal_app(cache)
    accounts = cca.get_accounts()
    if accounts:
        result = cca.acquire_token_silent(SCOPE, account=accounts[0])
        if result:
            session["token_cache"] = cache.serialize()
            return result
    return None

@app.route("/")
def home():
    if not session.get("user"):
        return render_template("login.html")
    return redirect("/formulario")

@app.route("/login")
def login():
    session["state"] = str(uuid.uuid4())
    auth_url = build_msal_app().get_authorization_request_url(
        SCOPE,
        state=session["state"],
        redirect_uri=REDIRECT_URI
    )
    return redirect(auth_url)

@app.route(REDIRECT_PATH)
def authorized():
    if request.args.get('state') != session.get("state"):
        return redirect("/")
    if "error" in request.args:
        return f"Error: {request.args['error_description']}"

    code = request.args.get("code")
    cache = msal.SerializableTokenCache()
    cca = build_msal_app(cache)

    result = cca.acquire_token_by_authorization_code(
        code,
        scopes=SCOPE,
        redirect_uri=REDIRECT_URI
    )

    if "access_token" in result:
        session["user"] = result.get("id_token_claims")
        session["access_token"] = result["access_token"]
        session["token_cache"] = cache.serialize()
        return redirect("/formulario")
    else:
        return "Error al obtener el token."

@app.route("/formulario", methods=["GET", "POST"])
def formulario():
    if not session.get("access_token"):
        return redirect("/")

    if request.method == "GET":
        return render_template("formulario.html")

    # POST: enviar correo
    data = request.form
    cuerpo = "\n".join([f"{k}: {v}" for k, v in data.items()])
    destinatario = os.environ.get("EMAIL_DESTINO")

    headers = {
        "Authorization": f"Bearer {session['access_token']}",
        "Content-Type": "application/json"
    }

    email_data = {
        "message": {
            "subject": "Formulario enviado",
            "body": {"contentType": "Text", "content": cuerpo},
            "toRecipients": [{"emailAddress": {"address": destinatario}}],
        },
        "saveToSentItems": "true"
    }

    response = requests.post(
        "https://graph.microsoft.com/v1.0/me/sendMail",
        headers=headers,
        json=email_data
    )

    if response.status_code == 202:
        return "✅ Correo enviado correctamente."
    else:
        return f"❌ Error al enviar correo: {response.text}"

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)