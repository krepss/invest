import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import numpy as np

# Configuração da página
st.set_page_config(page_title="Minha Carteira de FIIs", layout="wide")
st.title("📊 Controle e Projeção de FIIs")

# Inicializar a carteira na sessão (para não perder os dados ao interagir com a tela)
if 'carteira' not in st.session_state:
    st.session_state.carteira = pd.DataFrame(columns=["Ativo", "Quantidade", "Preco Medio"])

# ==========================
# BARRA LATERAL (INSERÇÃO)
# ==========================
st.sidebar.header("Adicionar Novo FII")
st.sidebar.markdown("*(Exemplo: MXRF11, HGLG11)*")

ticker_input = st.sidebar.text_input("Código do FII").upper()
qtd_input = st.sidebar.number_input("Quantidade", min_value=1, step=1)
pm_input = st.sidebar.number_input("Preço Médio (R$)", min_value=0.01, step=0.01)

if st.sidebar.button("Adicionar FII"):
    if ticker_input:
        novo_ativo = pd.DataFrame({
            "Ativo": [ticker_input], 
            "Quantidade": [qtd_input], 
            "Preco Medio": [pm_input]
        })
        st.session_state.carteira = pd.concat([st.session_state.carteira, novo_ativo], ignore_index=True)
        st.sidebar.success(f"{ticker_input} adicionado com sucesso!")
    else:
        st.sidebar.error("Por favor, insira o código do FII.")

if st.sidebar.button("Limpar Carteira"):
    st.session_state.carteira = pd.DataFrame(columns=["Ativo", "Quantidade", "Preco Medio"])
    st.sidebar.warning("Carteira zerada!")

# ==========================
# LÓGICA DE COTAÇÃO
# ==========================
@st.cache_data(ttl=3600) # Atualiza a cada 1 hora para não sobrecarregar
def buscar_cotacoes(tickers):
    precos = {}
    for t in tickers:
        try:
            # O yfinance exige o sufixo .SA para ativos da bolsa brasileira
            ticker_sa = f"{t}.SA"
            dados = yf.Ticker(ticker_sa).history(period="1d")
            if not dados.empty:
                precos[t] = dados['Close'].iloc[-1]
            else:
                precos[t] = 0.0
        except:
            precos[t] = 0.0
    return precos

# ==========================
# CORPO PRINCIPAL (ABAS)
# ==========================
aba_carteira, aba_projecao = st.tabs(["💼 Minha Carteira", "🚀 Projeção de Rendimentos"])

with aba_carteira:
    if not st.session_state.carteira.empty:
        df = st.session_state.carteira.copy()
        
        # Buscar preços atuais
        tickers_unicos = df['Ativo'].unique()
        precos_atuais = buscar_cotacoes(tickers_unicos)
        
        # Cálculos da carteira
        df['Preco Atual'] = df['Ativo'].map(precos_atuais)
        df['Custo Total'] = df['Quantidade'] * df['Preco Medio']
        df['Valor Atual'] = df['Quantidade'] * df['Preco Atual']
        df['Lucro/Prej (R$)'] = df['Valor Atual'] - df['Custo Total']
        df['Lucro/Prej (%)'] = ((df['Valor Atual'] / df['Custo Total']) - 1) * 100
        
        # Exibição de Métricas Gerais
        total_investido = df['Custo Total'].sum()
        patrimonio_atual = df['Valor Atual'].sum()
        lucro_total = patrimonio_atual - total_investido
        lucro_pct = (lucro_total / total_investido) * 100 if total_investido > 0 else 0
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Investido", f"R$ {total_investido:,.2f}")
        col2.metric("Patrimônio Atual", f"R$ {patrimonio_atual:,.2f}")
        col3.metric("Rentabilidade (Capital)", f"R$ {lucro_total:,.2f}", f"{lucro_pct:.2f}%")
        
        # Formatando a tabela para exibição bonita
        df_display = df.style.format({
            "Preco Medio": "R$ {:.2f}",
            "Preco Atual": "R$ {:.2f}",
            "Custo Total": "R$ {:.2f}",
            "Valor Atual": "R$ {:.2f}",
            "Lucro/Prej (R$)": "R$ {:.2f}",
            "Lucro/Prej (%)": "{:.2f}%"
        })
        
        st.dataframe(df_display, use_container_width=True)
        
        # Gráfico de Pizza da Composição
        st.subheader("Composição da Carteira")
        fig = px.pie(df, values='Valor Atual', names='Ativo', hole=0.4)
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.info("Sua carteira está vazia. Adicione ativos na barra lateral.")

with aba_projecao:
    st.header("Simulador de Bola de Neve (Juros Compostos)")
    st.markdown("Projete o crescimento da sua carteira baseado no reinvestimento de dividendos e aportes mensais.")
    
    col_p1, col_p2, col_p3 = st.columns(3)
    
    patrimonio_inicial = st.session_state.carteira['Custo Total'].sum() if not st.session_state.carteira.empty else 0.0
    
    aporte_mensal = col_p1.number_input("Aporte Mensal (R$)", value=500.0, step=100.0)
    dividend_yield_mensal = col_p2.number_input("Dividend Yield Mensal Esperado (%)", value=0.8, step=0.1) / 100
    anos = col_p3.number_input("Período (Anos)", value=10, min_value=1, step=1)
    
    meses = anos * 12
    historico_projecao = []
    
    patrimonio_acumulado = patrimonio_inicial
    
    for mes in range(1, meses + 1):
        rendimento = patrimonio_acumulado * dividend_yield_mensal
        patrimonio_acumulado += rendimento + aporte_mensal
        
        if mes % 12 == 0 or mes == meses: # Salvar dados anualmente para o gráfico ficar mais limpo
            historico_projecao.append({
                "Ano": mes // 12,
                "Patrimônio (R$)": patrimonio_acumulado,
                "Rendimento Mensal no Ano (R$)": rendimento
            })
            
    df_projecao = pd.DataFrame(historico_projecao)
    
    # Exibir resultados finais
    st.success(f"Em {anos} anos, seu patrimônio estimado será de **R$ {patrimonio_acumulado:,.2f}**, gerando uma renda mensal aproximada de **R$ {rendimento:,.2f}**.")
    
    # Gráfico da projeção
    fig_proj = px.bar(df_projecao, x="Ano", y="Patrimônio (R$)", title="Evolução do Patrimônio ao Longo do Tempo")
    st.plotly_chart(fig_proj, use_container_width=True)
