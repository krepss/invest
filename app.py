import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px

# Configuração da página
st.set_page_config(page_title="Minha Carteira de FIIs", layout="wide")
st.title("📊 Controle e Projeção de FIIs")

# Inicializar a carteira na sessão
if 'carteira' not in st.session_state:
    st.session_state.carteira = pd.DataFrame(columns=["Ativo", "Quantidade", "Preco Medio"])

# ==========================
# BARRA LATERAL (INSERÇÃO)
# ==========================
st.sidebar.header("Adicionar Novo FII")
st.sidebar.markdown("*(Exemplo: MXRF11, HGLG11)*")

ticker_input = st.sidebar.text_input("Código do FII").upper()
qtd_input = st.sidebar.number_input("Quantidade", min_value=1, step=1)
# O Preço Médio continua sendo necessário para você saber se está no lucro ou prejuízo
pm_input = st.sidebar.number_input("Seu Preço Médio (R$)", min_value=0.00, step=0.01)

if st.sidebar.button("Adicionar FII"):
    if ticker_input:
        # Verifica se o ativo já existe na carteira para não duplicar, mas sim somar (Opcional, aqui adiciona nova linha)
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
# LÓGICA DE BUSCA (PREÇO E DIVIDENDO)
# ==========================
@st.cache_data(ttl=3600) # Atualiza a cada 1 hora
def buscar_dados_mercado(tickers):
    dados = {}
    for t in tickers:
        try:
            ticker_sa = f"{t}.SA"
            ativo = yf.Ticker(ticker_sa)
            
            # Buscar Preço Atual
            hist = ativo.history(period="1d")
            preco_atual = hist['Close'].iloc[-1] if not hist.empty else 0.0
            
            # Buscar Último Dividendo Pago
            divs = ativo.dividends
            if not divs.empty:
                # Pega o último registro de dividendo
                ultimo_div = divs.iloc[-1]
            else:
                ultimo_div = 0.0
                
            dados[t] = {
                "Preco Atual": preco_atual,
                "Ultimo Dividendo": ultimo_div
            }
        except:
            dados[t] = {"Preco Atual": 0.0, "Ultimo Dividendo": 0.0}
    return dados

# ==========================
# CORPO PRINCIPAL (ABAS)
# ==========================
aba_carteira, aba_projecao = st.tabs(["💼 Minha Carteira", "🚀 Projeção de Rendimentos"])

with aba_carteira:
    if not st.session_state.carteira.empty:
        df = st.session_state.carteira.copy()
        
        # Buscar dados de mercado atuais
        tickers_unicos = df['Ativo'].unique()
        dados_mercado = buscar_dados_mercado(tickers_unicos)
        
        # Aplicar os dados buscados na tabela
        df['Preco Atual'] = df['Ativo'].apply(lambda x: dados_mercado[x]['Preco Atual'])
        df['Último Div. (R$)'] = df['Ativo'].apply(lambda x: dados_mercado[x]['Ultimo Dividendo'])
        
        # Novos Cálculos
        df['Custo Total'] = df['Quantidade'] * df['Preco Medio']
        df['Valor Atual'] = df['Quantidade'] * df['Preco Atual']
        df['Lucro/Prej (R$)'] = df['Valor Atual'] - df['Custo Total']
        df['Lucro/Prej (%)'] = ((df['Valor Atual'] / df['Custo Total']) - 1) * 100
        
        # Cálculo de Renda com base no último dividendo
        df['Renda Estimada (R$)'] = df['Quantidade'] * df['Último Div. (R$)']
        df['Dividend Yield Mensal (%)'] = (df['Último Div. (R$)'] / df['Preco Atual']) * 100
        
        # Exibição de Métricas Gerais
        total_investido = df['Custo Total'].sum()
        patrimonio_atual = df['Valor Atual'].sum()
        renda_mensal_total = df['Renda Estimada (R$)'].sum()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Patrimônio Atual", f"R$ {patrimonio_atual:,.2f}", f"Custo: R$ {total_investido:,.2f}")
        col2.metric("Renda Mensal Estimada", f"R$ {renda_mensal_total:,.2f}")
        col3.metric("Yield Médio Mensal da Carteira", f"{(renda_mensal_total / patrimonio_atual * 100) if patrimonio_atual > 0 else 0:.2f}%")
        
        # Reordenar colunas para ficar mais bonito
        cols_order = ['Ativo', 'Quantidade', 'Preco Medio', 'Preco Atual', 'Último Div. (R$)', 'Dividend Yield Mensal (%)', 'Custo Total', 'Valor Atual', 'Lucro/Prej (R$)', 'Lucro/Prej (%)', 'Renda Estimada (R$)']
        df = df[cols_order]

        # Formatando a tabela
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
        
        # Gráficos
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.subheader("Composição por Patrimônio")
            fig1 = px.pie(df, values='Valor Atual', names='Ativo', hole=0.4)
            st.plotly_chart(fig1, use_container_width=True)
        
        with col_g2:
            st.subheader("Maiores Pagadores de Renda")
            fig2 = px.pie(df, values='Renda Estimada (R$)', names='Ativo', hole=0.4)
            st.plotly_chart(fig2, use_container_width=True)
            
    else:
        st.info("Sua carteira está vazia. Adicione ativos na barra lateral.")

with aba_projecao:
    st.header("Simulador de Bola de Neve (Juros Compostos)")
    st.markdown("Projete o crescimento baseado no reinvestimento dos dividendos.")
    
    # Pega o Yield médio real da carteira se houver, se não usa 0.8% como padrão
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
                "Patrimônio (R$)": patrimonio_acumulado,
                "Renda Mensal no Ano (R$)": rendimento
            })
            
    df_projecao = pd.DataFrame(historico_projecao)
    
    st.success(f"Em {anos} anos, seu patrimônio estimado será de **R$ {patrimonio_acumulado:,.2f}**, gerando uma renda mensal de **R$ {rendimento:,.2f}**.")
    
    fig_proj = px.bar(df_projecao, x="Ano", y="Patrimônio (R$)", title="Evolução do Patrimônio")
    st.plotly_chart(fig_proj, use_container_width=True)
