import streamlit as st

# --- Credenciales de Usuario ---
# En una aplicación real, esto debería venir de una base de datos o de st.secrets.
USUARIOS = {
    "matias": "castelar2026",
    "pablo": "qwerty",
    "diego": "fusible123",
    "richard": "cabinero789"
}

# --- Funciones de Autenticación (basadas en st.session_state) ---

def verificar_credenciales(usuario, password):
    """Verifica si un usuario y contraseña son válidos."""
    usr = usuario.strip().lower()
    return usr in USUARIOS and USUARIOS[usr] == password

def logout():
    """Cierra la sesión del usuario limpiando el estado de la sesión."""
    st.session_state.logged_in = False
    st.session_state.usuario_activo = None
    # No es necesario st.rerun() aquí, la página que llama a logout se encargará.

def login():
    """Muestra el formulario de login y maneja el inicio de sesión."""
    st.title("🔑 Acceso - Depósito Castelar")
    with st.form("login_form"):
        usuario = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Iniciar Sesión"):
            if verificar_credenciales(usuario, password):
                # Si las credenciales son correctas, se marca al usuario como logueado en el estado de la sesión.
                st.session_state.logged_in = True
                st.session_state.usuario_activo = usuario.strip().capitalize()
                st.rerun() # Forzar recarga para que la app reconozca la nueva sesión.
            else:
                st.error("Usuario o contraseña incorrectos")

def check_authentication():
    """
    Verifica si el usuario está autenticado revisando el estado de la sesión.
    Devuelve True si está autenticado, False en caso contrario.
    """
    # Simplemente revisamos si la variable 'logged_in' es True en el estado de la sesión.
    # El uso de .get() evita errores si la variable aún no existe.
    return st.session_state.get('logged_in', False)