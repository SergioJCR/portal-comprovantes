import streamlit as st
import pandas as pd
from google import genai
from google.genai import types
from pypdf import PdfReader, PdfWriter
import json
import io
import time

# Configuração da página web
st.set_page_config(page_title="Plataforma Contábil IA", page_icon="🏢", layout="wide")

# --- CONEXÃO COM A NOVA API DO GOOGLE ---
def inicializar_ia():
    if "GEMINI_KEY" in st.secrets:
        token = st.secrets["GEMINI_KEY"]
    else:
        token = "COLE_AQUI_A_SUA_CHAVE_LOCAL" # Caso rode no PC
        
    if token in ["", "COLE_AQUI_A_SUA_CHAVE_LOCAL"]:
        st.error("⚠️ Token de API do Gemini não localizado nos Secrets do Streamlit.")
        return None
    try:
        # Usa o cliente moderno de alta performance do Google
        return genai.Client(api_key=token)
    except Exception as e:
        st.error(f"Erro ao conectar com servidor do Google: {e}")
        return None

# --- PROMPT CORPORATIVO BRASILEIRO ---
PROMPT_CONTABIL = """
Você é um auditor fiscal especialista em contabilidade brasileira.
Analise o documento bancário fornecido. Extraia TODOS os lançamentos válidos.

Regras Comerciais:
1. Saídas (pagamentos, transferências, débito, tarifas, juros) DEVEM ter o Valor Total negativo.
2. Entradas (recebimentos, PIX recebido, depósitos) DEVEM ter o Valor Total positivo.

Retorne estritamente uma lista em formato JSON padrão com as chaves exatas:
- "Data": DD/MM/AAAA
- "Banco": Nome do banco
- "Operação": Tipo de transação (Ex: PIX, TED, Boleto)
- "Descrição": Nome do Beneficiário ou Histórico do lançamento
- "CNPJ_Beneficiario": Apenas números do CNPJ ou CPF do favorecido (ou vazio "" se não houver)
- "Valor_Nominal": Número decimal positivo (Valor sem juros)
- "Juros_Multa": Número decimal positivo (Valor de juros/multa, ou 0.00)
- "Valor_Total": Número decimal final (Negativo para saídas, positivo para entradas)

Retorne APENAS o JSON puro, sem markdown como ```json ou textos explicativos.
"""

# --- MOTOR DE LEITURA BLINDADO EM LOTE ---
def processar_arquivo_em_lote(client, arquivo_carregado):
    # Força o uso do modelo mais rápido do mercado na nuvem
    model_name = 'gemini-2.5-flash'
    lancamentos_arquivo = []
    
    if arquivo_carregado.type == "application/pdf":
        reader = PdfReader(arquivo_carregado)
        total_paginas = len(reader.pages)
        tamanho_bloco = 10
        
        for i in range(0, total_paginas, tamanho_bloco):
            writer = PdfWriter()
            for num_pag in range(i, min(i + tamanho_bloco, total_paginas)):
                writer.add_page(reader.pages[num_pag])
                
            buffer_bloco = io.BytesIO()
            writer.write(buffer_bloco)
            
            documento_ia = types.Part.from_bytes(
                data=buffer_bloco.getvalue(),
                mime_type="application/pdf"
            )
            
            resposta = None
            for tentativa in range(3):
                try:
                    res = client.models.generate_content(
                        model=model_name,
                        contents=[documento_ia, PROMPT_CONTABIL]
                    )
                    if res and res.text:
                        resposta = res
                        break
                except Exception:
                    time.sleep(5)
            
            if respuesta:
                try:
                    texto_limpo = respuesta.text.strip().replace("```json", "").replace("```", "")
                    bloco_json = json.loads(texto_limpo)
                    if isinstance(bloco_json, list):
                        lancamentos_arquivo.extend(bloco_json)
                except:
                    continue
            
            time.sleep(12)
    else:
        bytes_imagem = arquivo_carregado.read()
        documento_ia = types.Part.from_bytes(
            data=bytes_imagem,
            mime_type=arquivo_carregado.type
        )
        try:
            res = client.models.generate_content(
                model=model_name,
                contents=[documento_ia, PROMPT_CONTABIL]
            )
            texto_limpo = res.text.strip().replace("```json", "").replace("```", "")
            lancamentos_arquivo = json.loads(texto_limpo)
        except:
            pass
            
    return lancamentos_arquivo

# --- GERADOR DE LAYOUT DOMÍNIO CONTÁBIL ---
def gerar_layout_dominio(dataframe):
    linhas_dominio = []
    for _, linha in dataframe.iterrows():
        data_formatada = str(linha.get('Data', '')).replace('/', '')
        try:
            valor_abs = abs(float(linha.get('Valor_Total', 0)))
        except:
            valor_abs = 0.0
        valor_texto = f"{valor_abs:.2f}".replace('.', ',')
        historico = str(linha.get('Descrição', 'PROCESSED BY IA')).upper()[:100]
        
        linha_txt = f"I|{data_formatada}|||{valor_texto}||{historico}|"
        linhas_dominio.append(linha_txt)
    return "\r\n".join(linhas_dominio)


# --- INTERFACE GRÁFICA MASTER ---
st.markdown("""
    <div style='background-color: #00469b; padding: 25px; border-radius: 6px; margin-bottom: 25px;'>
        <h1 style='color: white; margin: 0; font-size: 30px;'>Portal de Inteligência Contábil B2B</h1>
        <p style='color: #e0e0e0; margin: 5px 0 0 0;'>Processamento em Lote Avançado • Integração Direta com Sistema Domínio</p>
    </div>
""", unsafe_allow_html=True)

arquivos_lote = st.file_uploader(
    "Arraste múltiplos arquivos financeiros de uma só vez (PDFs longos ou imagens de comprovantes)", 
    type=["pdf", "png", "jpg", "jpeg"],
    accept_multiple_files=True
)

if arquivos_lote:
    st.info(f"📂 Total de documentos na fila: {len(arquivos_lote)} arquivo(s).")
    
    if st.button("🚀 Iniciar Processamento Estruturado em Massa", type="primary", use_container_width=True):
        client_ia = inicializar_ia()
        if client_ia:
            todos_dados_combinados = []
            barra_lote = st.progress(0, text="Preparando motores contábeis...")
            
            for index, arquivo in enumerate(arquivos_lote):
                porcentagem = (index + 1) / len(arquivos_lote)
                barra_lote.progress(porcentagem, text=f"Processando arquivo {index + 1} de {len(arquivos_lote)}: {arquivo.name}")
                
                resultado_arquivo = processar_arquivo_em_lote(client_ia, arquivo)
                if isinstance(resultado_arquivo, list):
                    todos_dados_combinados.extend(resultado_arquivo)
                elif isinstance(resultado_arquivo, dict):
                    todos_dados_combinados.append(resultado_arquivo)
                    
            if todos_dados_combinados:
                st.session_state['dados_lote_completos'] = pd.DataFrame(todos_dados_combinados)
                st.balloons()
                st.toast("Todos os lotes foram consolidados!", icon="✨")
            else:
                st.error("Não foi possível extrair dados válidos dos arquivos enviados.")

# --- PAINEL DE EXPORTAÇÃO COMPLETO ---
if 'dados_lote_completos' in st.session_state:
    df_final = st.session_state['dados_lote_completos']
    
    st.subheader("📋 Painel de Auditoria e Ajustes")
    df_revisado = st.data_editor(df_final, use_container_width=True)
    
    st.write("")
    st.subheader("📥 Central de Downloads Integrada")
    
    col1, col2 = st.columns(2)
    
    with col1:
        buffer_excel = io.BytesIO()
        with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
            df_revisado.to_excel(writer, index=False, sheet_name='Lote_IA')
        st.download_button(
            label="🟢 Baixar Planilha Unificada (.xlsx)",
            data=buffer_excel.getvalue(),
            file_name="lote_contabil_consolidado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
    with col2:
        texto_dominio = gerar_layout_dominio(df_revisado)
        st.download_button(
            label="🔵 Baixar Arquivo de Importação - Sistema Domínio (.txt)",
            data=texto_dominio,
            file_name="importacao_dominio_ia.txt",
            mime="text/plain",
            use_container_width=True
        )
