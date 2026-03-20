import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import qrcode
from PIL import Image, ImageDraw, ImageFont
import io
import altair as alt

st.set_page_config(page_title="InspMax", layout="wide")

# ==================== BANCO DE DADOS ====================
conn = sqlite3.connect("pecas.db", check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS users (
             id INTEGER PRIMARY KEY, nome TEXT UNIQUE, email TEXT, senha TEXT, 
             funcao TEXT, funcao_custom TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS pecas (
             qr_code TEXT PRIMARY KEY,
             tipo_peca TEXT,
             cor_atual TEXT,
             status TEXT,
             etapa TEXT,
             responsavel TEXT,
             cadastrado_por TEXT,          
             data_cadastro TEXT,
             resultado TEXT,
             data_conclusao TEXT,
             responsavel_conclusao TEXT,
             desenho_tecnico BLOB)''')   

c.execute('''CREATE TABLE IF NOT EXISTS historico (
             id INTEGER PRIMARY KEY,
             qr_code TEXT,
             tipo_peca TEXT,
             etapa TEXT,
             cor TEXT,
             status TEXT,
             responsavel TEXT,
             data TEXT,
             observacao TEXT)''')

conn.commit()

try:
    c.execute("ALTER TABLE pecas ADD COLUMN cadastrado_por TEXT")
    conn.commit()
    print("✅ Coluna 'cadastrado_por' adicionada com sucesso!")
except sqlite3.OperationalError:
    pass  

# ==================== USUÁRIO ADMIN ====================
c.execute("SELECT nome FROM users WHERE nome='admin'")
if not c.fetchone():
    c.execute("""INSERT INTO users 
                 (nome, email, senha, funcao, funcao_custom) 
                 VALUES (?,?,?,?,?)""",
              ("admin", None, "mec347", "Administrador", None))
    conn.commit()
    print("✅ Usuário admin criado automaticamente (senha: mec347)")
  
# ==================== PÁGINA PÚBLICA VIA QR CODE ====================
query_params = st.query_params
if "qr_code" in query_params:
    qr = query_params["qr_code"]
    if isinstance(qr, list):
        qr = qr[0]
    
    df = pd.read_sql(f"SELECT * FROM pecas WHERE qr_code = '{qr}'", conn)
    if not df.empty:
        peca = df.iloc[0]
        
        st.title(f"📋 Peça: **{qr}**")
        st.subheader(peca["tipo_peca"])
                
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"**Etapa atual:** {peca.get('etapa', '—')}")
            st.write(f"**Responsável:** {peca.get('responsavel', '—')}")
            st.write(f"**Data de cadastro:** {peca.get('data_cadastro', '—')}")
                
        # ==================== HISTÓRICO E COMENTÁRIOS ====================
        st.divider()
        st.subheader("📜 Histórico e Comentários")
        
        df_hist = pd.read_sql(f"""
            SELECT data AS 'Data/Hora', 
                   responsavel AS 'Responsável', 
                   etapa AS 'Etapa', 
                   status AS 'Status', 
                   observacao AS 'Comentário'
            FROM historico 
            WHERE qr_code = '{qr}' 
            ORDER BY data ASC
        """, conn)
        
        if not df_hist.empty:
            st.dataframe(df_hist, use_container_width=True, hide_index=True)
        else:
            st.info("Ainda não há comentários ou atualizações registradas.")
        
        # ==================== DESENHO TÉCNICO ====================
        st.divider()
        st.subheader("🖼️ Desenho Técnico")
        if peca.get("desenho_tecnico"):
            desenho_bytes = peca["desenho_tecnico"]
            try:
                with st.expander("🔍 Visualizar desenho ampliado (zoom)", expanded=False):
                    st.image(desenho_bytes, caption="Desenho Técnico", use_container_width=True)
                
                st.download_button(
                    label="⬇️ Baixar Desenho Técnico",
                    data=desenho_bytes,
                    file_name=f"desenho_{qr}.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True
                )
            except:
                st.download_button(
                    label="⬇️ Baixar Arquivo do Desenho",
                    data=desenho_bytes,
                    file_name=f"desenho_{qr}",
                    mime="application/octet-stream",
                    use_container_width=True
                )
        else:
            st.info("Nenhum desenho técnico cadastrado para esta peça.")
        
        # Botão para atualizar status
        if st.button("🔄 Atualizar Status desta peça", type="primary", use_container_width=True):
            st.session_state.scanned_qr = qr
            st.session_state.user = None
            st.query_params.clear()
            st.rerun()
        
        st.stop()
    else:
        st.error("❌ Peça não encontrada.")
        st.stop()

# ==================== SESSÃO E LOGIN ====================
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.title("🛠️ InspMax - Login")
    st.markdown("**Projeto Integrador MEC-3-47**")
    
    tab_login, tab_register, tab_recover = st.tabs(["🔑 Fazer Login", "📝 Cadastrar Novo Usuário", "🔓 Esqueci minha senha"])

    # ====================== LOGIN ======================
    with tab_login:
        with st.form("login_form"):
            nome_ou_email = st.text_input("Nome de usuário ou E-mail")
            senha = st.text_input("Senha", type="password")
            submitted = st.form_submit_button("Entrar", use_container_width=True)
            
            if submitted:
                if nome_ou_email and senha:
                    df_user = pd.read_sql(f"""
                        SELECT * FROM users
                        WHERE (nome = '{nome_ou_email}' OR email = '{nome_ou_email}')
                        AND senha = '{senha}'
                    """, conn)
                    if not df_user.empty:
                        st.session_state.user = df_user.iloc[0].to_dict()
                        st.rerun()
                    else:
                        st.error("Usuário, e-mail ou senha incorretos!")
                else:
                    st.error("Preencha todos os campos!")

    # ====================== CADASTRO ======================
    with tab_register:
        if st.session_state.get("cadastro_sucesso", False):
            st.success("✅ Usuário cadastrado com sucesso!", icon="🎉")
            st.session_state.cadastro_sucesso = False
        novo_nome = st.text_input("Nome completo (será seu login)")
        novo_email = st.text_input("E-mail válido")
        nova_senha = st.text_input("Escolha uma senha", type="password")
        funcao = st.selectbox("Função", ["Operador", "Inspetor de Qualidade", "Supervisor", "Gestor"])
        
        if st.button("Cadastrar Usuário", use_container_width=True):
            if novo_nome and novo_email and nova_senha:
                if "@" in novo_email and "." in novo_email and len(novo_email.split('@')) == 2:
                    try:
                        c.execute("""INSERT INTO users
                                     (nome, email, senha, funcao, funcao_custom)
                                     VALUES (?,?,?,?,?)""",
                                  (novo_nome, novo_email, nova_senha, funcao, None))
                        conn.commit()
                        st.session_state.cadastro_sucesso = True
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Esse nome ou e-mail já está cadastrado!")
                else:
                    st.error("Por favor, use um e-mail válido!")
            else:
                st.error("Preencha todos os campos!")

    # ====================== ESQUECI MINHA SENHA ======================
    with tab_recover:
        st.write("Informe seu **e-mail** ou **nome de usuário**:")
        recover_input = st.text_input("E-mail ou Nome")
        if st.button("Recuperar senha"):
            df = pd.read_sql(f"""
                SELECT nome, email FROM users
                WHERE nome = '{recover_input}' OR email = '{recover_input}'
            """, conn)
            if not df.empty:
                st.success(f"✅ Usuário encontrado: **{df.iloc[0]['nome']}**")
                nova_senha_recover = st.text_input("Digite sua **nova senha**", type="password")
                if st.button("Alterar senha"):
                    c.execute("UPDATE users SET senha = ? WHERE nome = ? OR email = ?",
                              (nova_senha_recover, recover_input, recover_input))
                    conn.commit()
                    st.success("Senha alterada com sucesso! Agora faça login.")
            else:
                st.error("E-mail ou nome não encontrado!")

    st.stop()

# ==================== MENU + SIDEBAR  ====================
try:
    logo_sidebar = Image.open("inspmax_logo.png")
    st.sidebar.image(logo_sidebar, width=200)  
except:
    st.sidebar.title("InspMax")

st.sidebar.success(f"👤 {st.session_state.user['nome']} ({st.session_state.user.get('funcao', '—')})")
if st.sidebar.button("🚪 Sair"):
    st.session_state.user = None
    st.rerun()

menu_options = [
    "📊 Dashboard Geral", "➕ Cadastrar Nova Peça", "🔄 Atualizar Status",
    "📋 Lista de Peças", "🗑️ Gerenciar Peças", "📖 Histórico por Peça",
    "📈 Produtividade", "🖨️ Gerar Etiqueta"
]
menu = st.sidebar.radio("Menu", menu_options, key="main_menu")
  
# ==================== CONFIGURAÇÕES GLOBAIS ====================
APP_URL = "https://mec347.streamlit.app"

CORES = {
    "Usinagem": "#1E90FF",
    "Inspeção Preliminar": "#FFD700",
    "Tratamento/Intermediário": "#FF8C00",
    "Inspeção Final": "#32CD32",
    "Retrabalho/Não Conforme": "#FF0000"
}

# ==================== ÁREA EXCLUSIVA DO ADMIN ====================
if st.session_state.user.get('nome') == 'admin':
    st.sidebar.divider()
    st.sidebar.subheader("🔴 Administração")

    # 1) Apagar todos os registros com confirmação Sim/Não
    if st.sidebar.button("🗑️ Apagar todos os registros", type="primary"):
        st.session_state.confirm_delete_all = True

    if st.session_state.get("confirm_delete_all"):
        st.sidebar.warning("⚠️ Deseja confirmar a exclusão TOTAL de TODOS os registros?")
        col_sim, col_nao = st.sidebar.columns(2)
        
        with col_sim:
            if st.button("✅ SIM, APAGAR TUDO", type="primary"):
                c.execute("DELETE FROM pecas")
                c.execute("DELETE FROM historico")
                conn.commit()
                st.success("✅ Todos os registros (peças, histórico e produtividade) foram apagados permanentemente!")
                del st.session_state.confirm_delete_all
                st.rerun()
        
        with col_nao:
            if st.button("❌ NÃO, CANCELAR"):
                del st.session_state.confirm_delete_all
                st.rerun()

    # 2) Gerenciar Usuários
    with st.sidebar.expander("👥 Gerenciar Usuários"):
        df_users = pd.read_sql("SELECT id, nome, funcao, funcao_custom FROM users", conn)
        st.dataframe(df_users, use_container_width=True, hide_index=True)

        user_to_manage = st.selectbox("Selecione o usuário para editar/excluir", df_users["nome"].tolist())
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✏️ Alterar Função"):
                st.session_state.edit_user = user_to_manage
        with col2:
            if st.button("🗑️ Excluir Usuário", type="primary"):
                st.session_state.delete_user = user_to_manage

        # Alterar função
        if st.session_state.get("edit_user") == user_to_manage:
            current_role = df_users[df_users["nome"] == user_to_manage]["funcao"].iloc[0]
            new_role = st.selectbox("Nova função", ["Operador", "Inspetor de Qualidade", "Outros"], 
                                  index=["Operador", "Inspetor de Qualidade", "Outros"].index(current_role) if current_role in ["Operador", "Inspetor de Qualidade", "Outros"] else 0)
            if st.button("Salvar nova função"):
                c.execute("UPDATE users SET funcao = ? WHERE nome = ?", (new_role, user_to_manage))
                conn.commit()
                st.success(f"Função de {user_to_manage} alterada com sucesso!")
                st.rerun()

        # Excluir usuário
        if st.session_state.get("delete_user") == user_to_manage:
            if st.button("✅ SIM, EXCLUIR USUÁRIO", type="primary"):
                c.execute("DELETE FROM users WHERE nome = ?", (user_to_manage,))
                conn.commit()
                st.success(f"Usuário {user_to_manage} excluído!")
                st.rerun()

# ==================== FUNÇÕES QR ====================
def criar_qr_pil(qr_code):
    full_url = f"{APP_URL}?qr_code={qr_code}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(full_url)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")

def gerar_etiqueta(qr_code, tipo_peca, cadastrado_por, responsavel, 
                   data_cadastro, etapa_atual, data_atualizacao, atualizado_por):
    
    cor_etapa = CORES.get(etapa_atual, "#1E90FF")
    
    largura, altura = 1200, 800
    img = Image.new("RGB", (largura, altura), color="white")
    draw = ImageDraw.Draw(img)
        
    draw.rectangle([0, 0, 65, altura], fill=cor_etapa)
        
    # ==================== LOGO  ====================
    try:
        logo_original = Image.open("inspmax_logo.png").convert("RGBA")
        logo = logo_original.resize((380, 200), Image.Resampling.LANCZOS)
        logo_com_fundo_branco = Image.new("RGBA", logo.size, (255, 255, 255, 255))
        logo_com_fundo_branco.paste(logo, (0, 0), logo)
        img.paste(logo_com_fundo_branco, (95, 8))
    except:
        draw.text((100, 60), "InspMax", fill="black", font=ImageFont.load_default())

    # ==================== QR CODE ====================
    qr_pil = criar_qr_pil(qr_code)
    qr_img = qr_pil.resize((265, 265))
    img.paste(qr_img, (830, 200))

    # ==================== FONTES ====================
    try:
        font_titulo = ImageFont.truetype("DejaVuSans-Bold.ttf", 40)
        font_normal = ImageFont.truetype("DejaVuSans-Bold.ttf", 30)
    except:
        font_titulo = font_normal = ImageFont.load_default()

    # ==================== FUNÇÃO DE TEXTO COM QUEBRA ====================
    def desenhar_texto(x, y_inicial, texto, font, cor="black", max_largura=720):
        if not texto.strip():
            return y_inicial + 10
        palavras = texto.split()
        linhas = []
        linha_atual = []
        for palavra in palavras:
            linha_teste = ' '.join(linha_atual + [palavra])
            largura_teste = draw.textlength(linha_teste, font=font)
            if largura_teste > max_largura and linha_atual:
                linhas.append(' '.join(linha_atual))
                linha_atual = [palavra]
            else:
                linha_atual.append(palavra)
        if linha_atual:
            linhas.append(' '.join(linha_atual))
        
        y = y_inicial
        for linha in linhas:
            draw.text((x, y), linha, fill=cor, font=font)
            y += font.size + 12
        return y + 8

    # ==================== TEXTOS ====================
    y = 215
    y = desenhar_texto(95, y, f"Nº: {qr_code}", font_titulo)
    y = desenhar_texto(95, y, f"Tipo: {tipo_peca}", font_normal)
    y = desenhar_texto(95, y, f"Cadastrado por: {cadastrado_por}", font_normal)
    y = desenhar_texto(95, y, f"Responsável: {responsavel}", font_normal)
    y = desenhar_texto(95, y, f"Data cadastro: {data_cadastro}", font_normal)
    y = desenhar_texto(95, y, f"Status: {etapa_atual}", font_normal, cor=cor_etapa)
    y = desenhar_texto(95, y, f"Data atualização: {data_atualizacao}", font_normal)
    desenhar_texto(95, y, f"Atualizado por: {atualizado_por}", font_normal)

    return img
                     
  # ==================== CADASTRAR NOVA PEÇA ====================
if menu == "➕ Cadastrar Nova Peça":
    if st.session_state.user['funcao'] not in ["Operador", "Gestor", "Supervisor", "Administrador"]:
        st.error("❌ Você não tem permissão para cadastrar peças.")
        st.stop()
    
    st.header("Cadastrar Nova Peça")
    
    if st.session_state.user['funcao'] in ["Gestor", "Supervisor", "Administrador"]:
        df_op = pd.read_sql("SELECT funcao, nome FROM users WHERE funcao = 'Operador'", conn)
        op_options = [f"{row['funcao']} - {row['nome']}" for _, row in df_op.iterrows()]
        responsavel_selecionado = st.selectbox("Operador responsável pela peça", op_options or ["Sem operador"], key="resp_cadastro")
    else:
        responsavel_selecionado = f"{st.session_state.user['funcao']} - {st.session_state.user['nome']}"
    
    cadastrado_por_full = f"{st.session_state.user['funcao']} - {st.session_state.user['nome']}"
    
    with st.form("cadastro_nova_peca", clear_on_submit=True):
        tipo = st.text_input("Tipo da Peça (ex: Eixo, Flange)", key="cad_tipo")
        etapa_inicial = st.selectbox("Etapa Inicial", ["Usinagem"], key="cad_etapa")
        obs = st.text_area("Observações iniciais", key="cad_obs")
        desenho = st.file_uploader("Desenho Técnico (PDF ou Imagem)", type=["pdf", "png", "jpg", "jpeg"], key="cad_desenho")
        submitted = st.form_submit_button("Cadastrar Peça")
        
        if submitted:
            qr_code = f"PECA-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            agora = datetime.now().strftime("%d/%m/%Y %H:%M")
            desenho_bytes = desenho.read() if desenho else None
            
            c.execute("""INSERT INTO pecas 
                         (qr_code, tipo_peca, cor_atual, status, etapa, responsavel, cadastrado_por,
                          data_cadastro, resultado, data_conclusao, responsavel_conclusao, desenho_tecnico)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (qr_code, tipo, etapa_inicial, "Em andamento", etapa_inicial, 
                       responsavel_selecionado, cadastrado_por_full, agora, None, None, None, desenho_bytes))
            
            c.execute("""INSERT INTO historico 
                         (qr_code, tipo_peca, etapa, cor, status, responsavel, data, observacao) 
                         VALUES (?,?,?,?,?,?,?,?)""",
                      (qr_code, tipo, etapa_inicial, etapa_inicial, "Início", st.session_state.user['nome'], agora, obs))
            conn.commit()
            
            st.success(f"✅ Peça cadastrada com sucesso! Código: **{qr_code}**")
            st.session_state.last_pdf = qr_code
            st.rerun()
  
    # DOWNLOAD DA ETIQUETA
    if st.session_state.get("last_pdf"):
        qr = st.session_state.last_pdf
        df = pd.read_sql(f"SELECT * FROM pecas WHERE qr_code = '{qr}'", conn)
        if not df.empty:
            peca = df.iloc[0]
            
            img = gerar_etiqueta(
                qr_code=qr,
                tipo_peca=peca["tipo_peca"],
                cadastrado_por=peca.get("cadastrado_por", peca["responsavel"]),
                responsavel=peca["responsavel"],
                data_cadastro=peca["data_cadastro"],
                etapa_atual=peca["etapa"],
                data_atualizacao=peca["data_cadastro"],
                atualizado_por=f"{st.session_state.user['funcao']} - {st.session_state.user['nome']}"
            )
            
            buf = io.BytesIO()
            img.save(buf, format="PDF", resolution=300)
            buf.seek(0)
            st.download_button(
                label="📄 **BAIXAR ETIQUETA EM PDF AGORA**",
                data=buf.getvalue(),
                file_name=f"etiqueta_{qr}.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )
            
            if st.button("🧹 Limpar formulário e preparar nova peça", type="secondary", use_container_width=True):
                for key in ["cad_tipo", "cad_etapa", "cad_obs", "cad_desenho", "last_pdf"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
          
# ==================== ATUALIZAR STATUS ====================
elif menu == "🔄 Atualizar Status":
    st.header("Atualizar Status da Peça")
    
    df_nao_concluidas = pd.read_sql("""
        SELECT qr_code, tipo_peca 
        FROM pecas 
        WHERE resultado IS NULL OR resultado = ''
        ORDER BY data_cadastro DESC
    """, conn)
   
    opcoes = ["🔍 Digitar código manualmente"] + [
        f"{row['qr_code']} - {row['tipo_peca']}" 
        for _, row in df_nao_concluidas.iterrows()
    ]
    
    escolha = st.selectbox(
        "Selecione a peça ou digite o código",
        opcoes
    )
  
    if escolha == "🔍 Digitar código manualmente":
        qr_input = st.text_input("Digite o QR Code da peça manualmente")
    else:
        qr_input = escolha.split(" - ")[0]   
    
    if qr_input:
        df = pd.read_sql(f"SELECT * FROM pecas WHERE qr_code = '{qr_input}'", conn)
        if not df.empty:
            peca = df.iloc[0]
            if peca.get('resultado') in ["Aprovado", "Reprovado"]:
                st.warning(f"✅ Esta peça já foi **{peca['resultado']}**")
            else:
                st.info(f"Peça atual: **{peca['tipo_peca']}** | Etapa: **{peca['etapa']}**")
                
                nova_etapa = st.selectbox("Nova Etapa", list(CORES.keys()))
                nova_obs = st.text_area("Observações")
                
                if st.button("Atualizar Status"):
                    if nova_etapa != peca['etapa']:
                        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
                        responsavel_full = f"{st.session_state.user['funcao']} - {st.session_state.user['nome']}"
                        c.execute("UPDATE pecas SET etapa=?, cor_atual=?, responsavel=?, data_cadastro=? WHERE qr_code=?",
                                  (nova_etapa, nova_etapa, responsavel_full, agora, qr_input))
                        c.execute("""INSERT INTO historico
                                     (qr_code, tipo_peca, etapa, cor, status, responsavel, data, observacao)
                                     VALUES (?,?,?,?,?,?,?,?)""",
                                  (qr_input, peca['tipo_peca'], nova_etapa, nova_etapa, "Atualizado", responsavel_full, agora, nova_obs))
                        conn.commit()
                        st.session_state.last_pdf = qr_input   
                        st.toast("✅ Status atualizado!", icon="🎉")
                        st.rerun()
                
                if peca['etapa'] == "Inspeção Final":
                    st.divider()
                    st.subheader("🎯 Concluir Peça")
                    resultado_final = st.radio("Resultado", ["Aprovado", "Reprovado"], horizontal=True)
                    obs_conclusao = st.text_area("Observações da conclusão")
                    
                    if st.button("✅ CONCLUIR PEÇA", type="primary"):
                        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
                        responsavel = f"{st.session_state.user['funcao']} - {st.session_state.user['nome']}"
                        c.execute("""UPDATE pecas
                                     SET resultado=?, responsavel_conclusao=?, data_conclusao=?
                                     WHERE qr_code=?""",
                                  (resultado_final, responsavel, agora, qr_input))
                        c.execute("""INSERT INTO historico
                                     (qr_code, tipo_peca, etapa, cor, status, responsavel, data, observacao)
                                     VALUES (?,?,?,?,?,?,?,?)""",
                                  (qr_input, peca['tipo_peca'], peca['etapa'], peca['cor_atual'],
                                   "Concluída", responsavel, agora, f"Resultado: {resultado_final} | {obs_conclusao}"))
                        conn.commit()
                        st.session_state.last_pdf = qr_input   
                        st.success(f"Peça concluída como **{resultado_final}**!")
                        st.rerun()
        else:
            st.error("QR Code não encontrado!")

    # ==================== BOTÃO DE DOWNLOAD DA ETIQUETA ====================
    if st.session_state.get("last_pdf"):
        qr = st.session_state.last_pdf
        df = pd.read_sql(f"SELECT * FROM pecas WHERE qr_code = '{qr}'", conn)
        if not df.empty:
            peca = df.iloc[0]
            
            img = gerar_etiqueta(
                qr_code=qr,
                tipo_peca=peca["tipo_peca"],
                cadastrado_por=peca.get("cadastrado_por", peca["responsavel"]),
                responsavel=peca["responsavel"],
                data_cadastro=peca["data_cadastro"],
                etapa_atual=peca["etapa"],
                data_atualizacao=peca.get("data_conclusao") or peca["data_cadastro"],
                atualizado_por=peca["responsavel"]
            )
            
            buf = io.BytesIO()
            img.save(buf, format="PDF", resolution=300)
            buf.seek(0)
            st.download_button(
                label="📄 **BAIXAR ETIQUETA ATUALIZADA**",
                data=buf.getvalue(),
                file_name=f"etiqueta_{qr}.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )
            
            if st.button("🧹 Limpar e preparar nova atualização", type="secondary", use_container_width=True):
                if "last_pdf" in st.session_state:
                    del st.session_state.last_pdf
                st.rerun()
              
# ==================== GERENCIAR PEÇAS ====================
elif menu == "🗑️ Gerenciar Peças":
    st.header("🗑️ Gerenciar Peças")
        
    df = pd.read_sql("""
        SELECT * FROM pecas 
        WHERE resultado IS NULL OR resultado = ''
    """, conn)
    
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        
        qr_para_acao = st.selectbox("Selecione o QR Code para excluir", df["qr_code"].tolist())
        
        if st.button("🗑️ EXCLUIR esta peça", type="primary"):
            st.session_state.to_delete = qr_para_acao
            st.rerun()
    else:
        st.info("Nenhuma peça em andamento. Todas as peças já foram concluídas.")
      
    if st.session_state.get("to_delete"):
        st.warning("⚠️ Tem certeza? Esta ação não pode ser desfeita.")
        col_sim, col_nao = st.columns(2)
        with col_sim:
            if st.button("✅ SIM, EXCLUIR", type="primary"):
                qr = st.session_state.to_delete
                c.execute("DELETE FROM pecas WHERE qr_code = ?", (qr,))
                c.execute("DELETE FROM historico WHERE qr_code = ?", (qr,))
                conn.commit()
                st.success(f"Peça {qr} excluída com sucesso!")
                del st.session_state.to_delete
                st.rerun()
        with col_nao:
            if st.button("❌ Cancelar"):
                del st.session_state.to_delete
                st.rerun()    
    
# ==================== DASHBOARD GERAL ====================
elif menu == "📊 Dashboard Geral":
    st.header("📊 Visão Geral da Produção")
    df = pd.read_sql("SELECT * FROM pecas WHERE resultado IS NULL OR resultado = ''", conn)
    if not df.empty:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Ativas", len(df))
        col2.metric("Usinagem", len(df[df["etapa"] == "Usinagem"]))
        col3.metric("Inspeção Final", len(df[df["etapa"] == "Inspeção Final"]))
        col4.metric("Retrabalho", len(df[df["etapa"] == "Retrabalho/Não Conforme"]))
        
        color_scale = alt.Scale(domain=list(CORES.keys()), range=list(CORES.values()))
        chart = alt.Chart(df).mark_bar(size=40).encode(
            x=alt.X("etapa:N", sort=list(CORES.keys())),
            y=alt.Y("count():Q"),
            color=alt.Color("etapa:N", scale=color_scale)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Nenhuma peça ativa.")

# ==================== LISTA DE PEÇAS ====================
elif menu == "📋 Lista de Peças":
    st.header("Lista Completa de Peças")
    df_andamento = pd.read_sql("""
        SELECT qr_code, tipo_peca, etapa, cor_atual, status, responsavel, data_cadastro 
        FROM pecas WHERE resultado IS NULL OR resultado = ''
    """, conn)
    
    if not df_andamento.empty:
        df_andamento = df_andamento.rename(columns={
            "tipo_peca": "Tipo da Peça",
            "etapa": "Etapa",
            "cor_atual": "Cor",
            "status": "Status",
            "responsavel": "Responsável",
            "data_cadastro": "Data Atualização"
        })
        df_andamento = df_andamento[["qr_code", "Tipo da Peça", "Etapa", "Cor", "Status", "Responsável", "Data Atualização"]]
    
    df_concluidas = pd.read_sql("SELECT * FROM pecas WHERE resultado IS NOT NULL", conn)
    
    tab_and, tab_conc = st.tabs(["Peças em Andamento", "Peças Concluídas"])
    
    with tab_and:
        if not df_andamento.empty:
            st.dataframe(df_andamento, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma peça em andamento no momento.")
    
    with tab_conc:
        if not df_concluidas.empty:
            df_display = df_concluidas[['qr_code', 'tipo_peca', 'resultado', 'responsavel', 
                                       'responsavel_conclusao', 'data_cadastro', 'data_conclusao']].rename(columns={
                'tipo_peca': 'Nome da Peça', 'resultado': 'Status',
                'responsavel': 'Responsável Cadastro',
                'responsavel_conclusao': 'Quem Concluiu'
            })
            tab_apr, tab_rep = st.tabs(["✅ Aprovadas", "❌ Reprovadas"])
            with tab_apr:
                apr = df_display[df_display['Status'] == "Aprovado"]
                if not apr.empty:
                    st.dataframe(apr, use_container_width=True, hide_index=True)
                else:
                    st.info("Nenhuma aprovada.")
            with tab_rep:
                rep = df_display[df_display['Status'] == "Reprovado"]
                if not rep.empty:
                    st.dataframe(rep, use_container_width=True, hide_index=True)
                else:
                    st.info("Nenhuma reprovada.")
        else:
            st.info("Nenhuma peça concluída ainda.")

# ==================== HISTÓRICO POR PEÇA ====================
elif menu == "📖 Histórico por Peça":
    st.header("Histórico Completo")
        
    df_andamento = pd.read_sql("""
        SELECT qr_code, tipo_peca 
        FROM pecas 
        WHERE resultado IS NULL OR resultado = ''
    """, conn)
      
    df_concluidas = pd.read_sql("""
        SELECT qr_code, tipo_peca 
        FROM pecas 
        WHERE resultado IS NOT NULL
    """, conn)
    
    tab_and, tab_conc = st.tabs(["Peças em Andamento", "Peças Concluídas"])
    
    with tab_and:
        if not df_andamento.empty:
            lista_and = df_andamento["qr_code"].tolist()
            qr_sel_and = st.selectbox("Selecione o QR Code (Em Andamento)", lista_and, key="hist_and")
            if qr_sel_and:
                hist = pd.read_sql(f"""SELECT 
                                       tipo_peca AS "Tipo_Peca",
                                       etapa AS "Etapa",
                                       cor AS "Cor",
                                       status,
                                       responsavel,
                                       data,
                                       observacao 
                                       FROM historico 
                                       WHERE qr_code='{qr_sel_and}' 
                                       ORDER BY data""", conn)
                st.dataframe(hist, use_container_width=True)
        else:
            st.info("Nenhuma peça em andamento.")
    
    with tab_conc:
        if not df_concluidas.empty:
            lista_conc = df_concluidas["qr_code"].tolist()
            qr_sel_conc = st.selectbox("Selecione o QR Code (Concluídas)", lista_conc, key="hist_conc")
            if qr_sel_conc:
                hist = pd.read_sql(f"""SELECT 
                                       tipo_peca AS "Tipo_Peca",
                                       etapa AS "Etapa",
                                       cor AS "Cor",
                                       status,
                                       responsavel,
                                       data,
                                       observacao 
                                       FROM historico 
                                       WHERE qr_code='{qr_sel_conc}' 
                                       ORDER BY data""", conn)
                st.dataframe(hist, use_container_width=True)
        else:
            st.info("Nenhuma peça concluída ainda.")

# ==================== PRODUTIVIDADE ====================
elif menu == "📈 Produtividade":
    st.header("📈 Produtividade da Equipe")
    
    df_hist = pd.read_sql("""
        SELECT h.*, p.etapa as etapa_atual,
               substr(h.data,7,4) || '-' || substr(h.data,4,2) as mes
        FROM historico h 
        LEFT JOIN pecas p ON h.qr_code = p.qr_code
    """, conn)
    
    if df_hist.empty:
        st.info("Ainda não há dados de produtividade.")
    else:
        # Filtro sem duplicação do mês atual
        meses_unicos = sorted(df_hist['mes'].unique(), reverse=True)
        mes_atual = datetime.now().strftime("%Y-%m")
        
        meses_anteriores = [m for m in meses_unicos if m != mes_atual]
        
        opcoes_filtro = ["Mês Atual", "Acumulado do Ano", "─"] + meses_anteriores
        
        periodo = st.selectbox("Período", opcoes_filtro, index=0)
        
        # Aplica filtro
        if periodo == "Mês Atual":
            df_filtrado = df_hist[df_hist['mes'] == mes_atual]
        elif periodo == "Acumulado do Ano":
            df_filtrado = df_hist.copy()
        elif periodo != "─":
            df_filtrado = df_hist[df_hist['mes'] == periodo]
        else:
            df_filtrado = df_hist.copy()

        tab_op, tab_insp, tab_top3, tab_geral = st.tabs(["🔧 Operadores", "🔍 Inspetores", "🏆 Top 3", "📊 Ranking Geral da Fábrica"])

        # ====================== OPERADORES ======================
        with tab_op:
            st.subheader("Desempenho dos Operadores")
            op = df_filtrado[df_filtrado['status'] == 'Início'].groupby('responsavel').agg(
                Total_Cadastradas=('qr_code', 'nunique')
            ).reset_index()
            
            concluidas = df_filtrado[df_filtrado['status'] == 'Concluída'].groupby('responsavel').agg(
                Concluidas=('qr_code', 'nunique'),
                Aprovadas=('status', lambda x: (x == 'Concluída').sum()),
                Retrabalho=('etapa_atual', lambda x: (x == 'Retrabalho/Não Conforme').sum())
            ).reset_index()
            
            op = op.merge(concluidas, on='responsavel', how='left').fillna(0)
            op = op.astype({'Total_Cadastradas': 'int', 'Concluidas': 'int', 'Aprovadas': 'int', 'Retrabalho': 'int'})
            
            op['Taxa_Conclusao_%'] = (op['Concluidas'] / op['Total_Cadastradas'] * 100).round(1)
            op['Taxa_Aprovacao_%'] = (op['Aprovadas'] / op['Concluidas'] * 100).round(1) if op['Concluidas'].sum() > 0 else 0
            
            st.dataframe(op, use_container_width=True)

        # ====================== INSPETORES ======================
        with tab_insp:
            st.subheader("Desempenho dos Inspetores")
            insp = df_filtrado[df_filtrado['status'].isin(['Atualizado', 'Concluída'])].groupby('responsavel').agg(
                Total_Inspecionadas=('id', 'count'),
                Aprovadas=('status', lambda x: (x == 'Concluída').sum()),
                Reprovadas=('status', lambda x: (x == 'Concluída').sum())
            ).reset_index()
            
            insp = insp.astype({'Total_Inspecionadas': 'int', 'Aprovadas': 'int', 'Reprovadas': 'int'})
            insp['Taxa_Aprovacao_%'] = (insp['Aprovadas'] / insp['Total_Inspecionadas'] * 100).round(1)
            insp['Taxa_Reprovacao_%'] = (insp['Reprovadas'] / insp['Total_Inspecionadas'] * 100).round(1)
            
            st.dataframe(insp, use_container_width=True)

        # ====================== TOP 3 ======================
        with tab_top3:
            st.subheader("🏆 Top 3 Operadores")
            top_op = op.nlargest(3, 'Total_Cadastradas')[['responsavel', 'Total_Cadastradas', 'Taxa_Aprovacao_%', 'Taxa_Conclusao_%']]
            st.dataframe(top_op, use_container_width=True)
            
            st.subheader("🏆 Top 3 Inspetores")
            top_insp = insp.nlargest(3, 'Total_Inspecionadas')[['responsavel', 'Total_Inspecionadas', 'Taxa_Aprovacao_%']]
            st.dataframe(top_insp, use_container_width=True)

        # ====================== RANKING GERAL ======================
        with tab_geral:
            st.subheader("📊 Ranking Geral da Fábrica")
            geral = pd.DataFrame({
                'Métrica': ['Total de Peças Cadastradas', 'Em Inspeção Preliminar', 'Em Retrabalho/Não Conforme', 
                           'Em Inspeção Final', 'Aprovadas', 'Reprovadas'],
                'Quantidade': [
                    len(df_filtrado[df_filtrado['status'] == 'Início']),
                    len(df_filtrado[df_filtrado['etapa_atual'] == 'Inspeção Preliminar']),
                    len(df_filtrado[df_filtrado['etapa_atual'] == 'Retrabalho/Não Conforme']),
                    len(df_filtrado[df_filtrado['etapa_atual'] == 'Inspeção Final']),
                    len(df_filtrado[df_filtrado['status'] == 'Concluída']),
                    len(df_filtrado[df_filtrado['status'] == 'Concluída'])
                ]
            })
            st.dataframe(geral, use_container_width=True, hide_index=True)

# ==================== GERAR ETIQUETA ====================
elif menu == "🖨️ Gerar Etiqueta":
    st.header("Gerar Etiqueta Colorida")
    
    df_nao_concluidas = pd.read_sql("""
        SELECT qr_code, tipo_peca 
        FROM pecas 
        WHERE resultado IS NULL OR resultado = ''
        ORDER BY data_cadastro DESC
    """, conn)
      
    opcoes = ["🔍 Digitar código manualmente"] + [
        f"{row['qr_code']} - {row['tipo_peca']}" 
        for _, row in df_nao_concluidas.iterrows()
    ]
    
    escolha = st.selectbox("Selecione a peça ou digite o código", opcoes)
        
    if escolha == "🔍 Digitar código manualmente":
        qr_input = st.text_input("Digite o QR Code da peça manualmente")
    else:
        qr_input = escolha.split(" - ")[0]
    
    if qr_input:
        df = pd.read_sql(f"SELECT * FROM pecas WHERE qr_code = '{qr_input}'", conn)
        if not df.empty:
            peca = df.iloc[0]
            
            if st.button("Gerar Etiqueta"):
                img = gerar_etiqueta(
                    qr_code=qr_input,
                    tipo_peca=peca["tipo_peca"],
                    cadastrado_por=peca.get("cadastrado_por", peca["responsavel"]),
                    responsavel=peca["responsavel"],
                    data_cadastro=peca["data_cadastro"],
                    etapa_atual=peca["etapa"],
                    data_atualizacao=peca.get("data_conclusao") or peca["data_cadastro"],
                    atualizado_por=peca["responsavel"]
                )
                st.image(img, caption="Pré-visualização da Etiqueta", use_container_width=True)
                
                buf = io.BytesIO()
                img.save(buf, format="PDF", resolution=300)
                buf.seek(0)
                st.download_button(
                    label="📄 Baixar Etiqueta",
                    data=buf.getvalue(),
                    file_name=f"etiqueta_{qr_input}.pdf",
                    mime="application/pdf"
                )
        else:
            st.error("QR Code não encontrado!")
    else:
        st.info("Selecione ou digite um QR Code para gerar a etiqueta.")
