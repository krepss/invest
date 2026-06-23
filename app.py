import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import numpy as np
from github import Github
import io

# ==========================
# CONFIGURAÇÃO DA PÁGINA
# ==========================
st.set_page_config(page_title="A Minha Carteira de FIIs", layout="wide")
st.title("📊 Controlo e Projeção de FIIs")

# ==========================
# INTEGRAÇÃO COM O GITHUB (LEITURA E ESCRITA)
# ==========================
ARQUIVO_DADOS = "carteira.csv"

def carregar_carteira_github():
    """Lê o ficheiro CSV diretamente do repositório do GitHub."""
    try:
        g = Github(st.secrets["GITHUB_TOKEN"])
        repo = g.get_repo(st.secrets["GITHUB_REPO"])
        file_content = repo.get_contents(ARQUIVO_DADOS)
        
        # O GitHub devolve o ficheiro em base64, precisamos descodificar
        csv_data = file_content.decoded_content.decode('utf-8')
        return pd.read_csv(io.StringIO(csv_data))
    except Exception as e:
        # Se der erro (ex: o ficheiro não existe ainda), cria um vazio
        return pd.DataFrame(columns=["Ativo", "Quantidade", "Preco Medio"])

def salvar_carteira_github(df):
    """Guarda ou atualiza o DataFrame no ficheiro CSV no GitHub."""
    try:
        g = Github(st.secrets["GITHUB_TOKEN"])
        repo = g.get_repo(st.secrets["GITHUB_REPO"])
        
        # Converte o DataFrame para formato de texto CSV
        csv_data = df.to_csv(index=False)
        
        try:
            # Tenta encontrar o ficheiro para o atualizar (precisa do 'sha' do ficheiro atual)
            file = repo.get_contents(ARQUIVO_DADOS)
            repo.update_file(
                path=ARQUIVO_DADOS,
                message="Atualizando carteira via Streamlit App",
                content=csv_data,
                sha=file.sha
            )
        except:
            # Se o ficheiro não existir no GitHub, cria um novo
            repo.create_file(
                path=ARQUIVO_DADOS,
                message="Criando ficheiro de carteira via Streamlit App",
                content=csv_data
            )
        return True
    except Exception as e:
        st.error(f"Erro ao salvar no GitHub: {e}")
        return False

# ==========================
# INICIALIZAÇÃO DA SESSÃO
# ==========================
if 'carteira' not in st.session_state:
    with st.spinner("A carregar dados do GitHub..."):
        st.session_state.carteira = carregar_carteira_github()

# ==========================
# BARRA LATERAL (INSERÇÃO E REMOÇÃO)
# ==========================
st.sidebar.header("Adicionar Novo FII")
ticker_input = st.sidebar.text_input("Código do FII (ex: MXRF11)").upper()
qtd_input = st.sidebar.number_input("Quantidade", min_value=1, step=1)
st.sidebar.markdown("*(Deixe 0 se quiser usar o Preço Atual de mercado como Preço Médio)*")
pm_input = st.sidebar.number_input("O seu Preço Médio (R$)", min_value=0.00, step=0.01, value=0.00)

if st.sidebar.button("Adicionar FII"):
    if ticker_input:
        novo_ativo = pd.DataFrame({
            "Ativo": [ticker_input], 
            "Quantidade": [qtd_input], 
            "Preco Medio": [pm_input]
        })
        st.session_state.carteira = pd.concat([st.session_state.carteira, novo_ativo], ignore_index=True)
        
        with st.spinner("A gravar no GitHub..."):
            salvar_carteira_github(st.session_state.carteira)
            
        st.sidebar.success(f"{ticker_input} adicionado!")
        st.rerun() # Atualiza a página imediatamente
    else:
        st.sidebar.error("Por favor, introduza o código do FII.")

st.sidebar.markdown("---")
st.sidebar.header("Remover FII")
if not st.session_state.carteira.empty:
    opcoes_ativos = st.session_state.carteira["Ativo"].unique().tolist()
    ativo_remover = st.sidebar.selectbox("Selecione o FII", opcoes_ativos)
    
    if st.sidebar.button("Remover Ativo"):
        # Mantém na carteira apenas os ativos diferentes do selecionado
        st.session_state.carteira = st.session_state.carteira[st.session_state.carteira["Ativo"] != ativo_remover]
        
        with st.spinner("A apagar do GitHub..."):
            salvar_carteira_github(st.session_state.carteira)
            
        st.sidebar.warning(f"{ativo_remover} removido da carteira!")
        st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("Limpar Toda a Carteira"):
    st.session_state.carteira = pd.DataFrame(columns=["Ativo", "Quantidade", "Preco Medio"])
    with st.spinner("A apagar ficheiro no GitHub..."):
        salvar_carteira_github(st.session_state.carteira)
    st.rerun()

# ==========================
# LÓGICA DE BUSCA (PREÇO E DIVIDENDO)
# ==========================
@st.cache_data(ttl=3600)
def buscar_dados_mercado(tickers):
    dados = {}
    for t in tickers:
        try:
            ticker_sa = f"{t}.SA"
            ativo = yf.Ticker(ticker_sa)
            hist = ativo.history(period="1d")
            preco_atual = hist['Close'].iloc[-1] if not hist.empty else 0.0
            divs = ativo.dividends
            ultimo_div = divs.iloc[-1] if not divs.empty else 0.0
            dados[t] = {"Preco Atual": preco_atual, "Ultimo Dividendo": ultimo_div}
        except:
            dados[t] = {"Preco Atual": 0.0, "Ultimo Dividendo": 0.0}
    return dados

# ==========================
# CORPO PRINCIPAL (SEPARADORES)
# ==========================
aba_carteira, aba_projecao = st.tabs(["💼 A Minha Carteira", "🚀 Projeção de Rendimentos"])

with aba_carteira:
    if not st.session_state.carteira.empty:
        df = st.session_state.carteira.copy()
        
        tickers_unicos = df['Ativo'].unique()
        dados_mercado = buscar_dados_mercado(tickers_unicos)
        
        df['Preco Atual'] = df['Ativo'].apply(lambda x: dados_mercado[x]['Preco Atual'])
        df['Último Div. (R$)'] = df['Ativo'].apply(lambda x: dados_mercado[x]['Ultimo Dividendo'])
        df['Preco Medio'] = np.where(df['Preco Medio'] == 0, df['Preco Atual'], df['Preco Medio'])
        
        df['Custo Total'] = df['Quantidade'] * df['Preco Medio']
        df['Valor Atual'] = df['Quantidade'] * df['Preco Atual']
        df['Lucro/Prej (R$)'] = df['Valor Atual'] - df['Custo Total']
        
        df['Lucro/Prej (%)'] = ((df['Valor Atual'] / df['Custo Total'].replace(0, np.nan)) - 1) * 100
        df['Lucro/Prej (%)'] = df['Lucro/Prej (%)'].fillna(0.0)
        
        df['Renda Estimada (R$)'] = df['Quantidade'] * df['Último Div. (R$)']
        df['Dividend Yield Mensal (%)'] = (df['Último Div. (R$)'] / df['Preco Atual'].replace(0, np.nan)) * 100
        df['Dividend Yield Mensal (%)'] = df['Dividend Yield Mensal (%)'].fillna(0.0)
        
        total_investido = df['Custo Total'].sum()
        patrimonio_atual = df['Valor Atual'].sum()
        renda_mensal_total = df['Renda Estimada (R$)'].sum()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Património Atual", f"R$ {patrimonio_atual:,.2f}", f"Custo: R$ {total_investido:,.2f}")
        col2.metric("Renda Mensal Estimada", f"R$ {renda_mensal_total:,.2f}")
        col3.metric("Yield Médio Mensal da Carteira", f"{(renda_mensal_total / patrimonio_atual * 100) if patrimonio_atual > 0 else 0:.2f}%")
        
        cols_order = ['Ativo', 'Quantidade', 'Preco Medio', 'Preco Atual', 'Último Div. (R$)', 'Dividend Yield Mensal (%)', 'Custo Total', 'Valor Atual', 'Lucro/Prej (R$)', 'Lucro/Prej (%)', 'Renda Estimada (R$)']
        df = df[cols_order]

        df_display = df.style.format({
            "Preco Medio": "R$ {:.2f}",
            "Preco Atual": "R$ {:.2f}",
            "Último Div. (R$)": "R$ {:.4f}",
            "Dividend Yield Mensal (%)": "{:.2f}%",
            "Custo Total": "R$ {:.2f}",
            "Valor Atual": "R$ {:.2f}",
            "Lucro/Prej (R$)": "R$ {:.2f}",
            "Lucro/Prej (%)": "{:.2f}%",
            "Renda Estimada (R$)": "R$ {:.2f}"
        })
        
        st.dataframe(df_display, use_container_width=True)
        
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.subheader("Composição por Património")
            fig1 = px.pie(df, values='Valor Atual', names='Ativo', hole=0.4)
            st.plotly_chart(fig1, use_container_width=True)
        
        with col_g2:
            st.subheader("Maiores Pagadores de Renda")
            fig2 = px.pie(df, values='Renda Estimada (R$)', names='Ativo', hole=0.4)
            st.plotly_chart(fig2, use_container_width=True)
            
    else:
        st.info("A sua carteira está vazia. Adicione ativos na barra lateral.")

with aba_projecao:
    st.header("Simulador de Bola de Neve (Juros Compostos)")
    st.markdown("Projete o crescimento baseado no reinvestimento dos dividendos.")
    
    yield_padrao = (renda_mensal_total / patrimonio_atual * 100) if not st.session_state.carteira.empty and patrimonio_atual > 0 else 0.8
    
    col_p1, col_p2, col_p3 = st.columns(3)
    
    patrimonio_inicial = patrimonio_atual if not st.session_state.carteira.empty else 0.0
    
    aporte_mensal = col_p1.number_input("Aporte Mensal (R$)", value=500.0, step=100.0)
    dividend_yield_mensal = col_p2.number_input("DY Mensal Esperado (%)", value=float(f"{yield_padrao:.2f}"), step=0.1) / 100
    anos = col_p3.number_input("Período (Anos)", value=10, min_value=1, step=1)
    
    meses = anos * 12
    historico_projecao = []
    patrimonio_acumulado = patrimonio_inicial
    
    for mes in range(1, meses + 1):
        rendimento = patrimonio_acumulado * dividend_yield_mensal
        patrimonio_acumulado += rendimento + aporte_mensal
        
        if mes % 12 == 0 or mes == meses:
            historico_projecao.append({
                "Ano": mes // 12,
                "Património (R$)": patrimonio_acumulado,
                "Renda Mensal no Ano (R$)": rendimento
            })
            
    df_projecao = pd.DataFrame(historico_projecao)
    
    st.success(f"Em {anos} anos, o seu património estimado será de **R$ {patrimonio_acumulado:,.2f}**, gerando uma renda mensal de **R$ {rendimento:,.2f}**.")
    
    fig_proj = px.bar(df_projecao, x="Ano", y="Património (R$)", title="Evolução do Património")
    st.plotly_chart(fig_proj, use_container_width=True)
