import streamlit as st
import requests
import xml.etree.ElementTree as ET
import json
import google.generativeai as genai

# Configuração da página e visual
st.set_page_config(page_title="Leitor do arXiv", page_icon="📄", layout="centered")

# Puxa a chave da API dos "Secrets" do Streamlit (vamos configurar no Passo 3)
API_KEY = st.secrets.get("GEMINI_API_KEY")

if API_KEY:
    genai.configure(api_key=API_KEY)
else:
    st.error("⚠️ Chave GEMINI_API_KEY não configurada nos Secrets do Streamlit.")

CATEGORIAS = {
    "Astrofísica da Terra e Planetária (astro-ph.EP)": "astro-ph.EP",
    "Astrofísica Galáctica (astro-ph.GA)": "astro-ph.GA",
    "Cosmologia e Astrofísica (astro-ph.CO)": "astro-ph.CO",
    "Física Espacial (physics.space-ph)": "physics.space-ph",
    "Inteligência Artificial (cs.AI)": "cs.AI",
    "Computação e Linguagem / NLP (cs.CL)": "cs.CL",
    "Visão Computacional (cs.CV)": "cs.CV",
    "Engenharia de Software (cs.SE)": "cs.SE",
}

st.title("📄 Leitor do arXiv")
st.markdown("Artigos de **Astronomia, Espaço e Tecnologia** traduzidos com IA.")

# Interface de seleção
selected_cat_name = st.selectbox("Escolha a categoria:", list(CATEGORIAS.keys()))
selected_cat_code = CATEGORIAS[selected_cat_name]

if st.button("Buscar Artigos"):
    if not API_KEY:
        st.stop()
        
    # O st.spinner mantém o usuário avisado enquanto o processo roda sem limite de tempo
    with st.spinner("Buscando artigos no arXiv e traduzindo... Isso pode levar uns segundos, mas aqui não cai! 🚀"):
        
        # 1. Busca os dados no arXiv (Voltamos para 5 resultados já que não há limite de tempo)
        url = f"https://export.arxiv.org/api/query?search_query=cat:{selected_cat_code}&sortBy=submittedDate&sortOrder=descending&max_results=5"
        response = requests.get(url)
        
        if response.status_code != 200:
            st.error("Erro ao buscar no arXiv.")
            st.stop()
            
        root = ET.fromstring(response.text)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        entries = []
        for entry in root.findall('atom:entry', ns):
            arxiv_id = entry.find('atom:id', ns).text.split('/')[-1]
            title = entry.find('atom:title', ns).text.replace('\n', ' ').strip()
            summary = entry.find('atom:summary', ns).text.replace('\n', ' ').strip()
            published = entry.find('atom:published', ns).text.split('T')[0]
            
            authors_list = [author.find('atom:name', ns).text for author in entry.findall('atom:author', ns)]
            
            entries.append({
                "id": arxiv_id,
                "title": title,
                "summary": summary,
                "authors": ", ".join(authors_list),
                "published": published
            })
            
        if not entries:
            st.warning("Nenhum artigo encontrado para esta categoria.")
            st.stop()
            
        # 2. Chama o Gemini para traduzir com JSON Schema Rígido
        prompt = f"""Traduza os títulos e resumos abaixo para o Português do Brasil.
        Para os resumos, faça uma tradução concisa e direta (no máximo 3 a 4 frases).
        Conteúdo: {json.dumps([{"id": e["id"], "title": e["title"], "summary": e["summary"]} for e in entries])}"""
        
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            res = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema={
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "id": {"type": "STRING"},
                                "title_pt": {"type": "STRING"},
                                "summary_pt": {"type": "STRING"}
                            },
                            "required": ["id", "title_pt", "summary_pt"]
                        }
                    }
                )
            )
            
            translated_data = json.loads(res.text)
            trans_dict = {item['id']: item for item in translated_data}
            
            st.success(f"Exibindo {len(entries)} artigos mais recentes!")
            st.divider()
            
            # 3. Renderiza os resultados na tela
            for paper in entries:
                paper_id = paper['id']
                title_pt = trans_dict.get(paper_id, {}).get("title_pt", paper["title"])
                summary_pt = trans_dict.get(paper_id, {}).get("summary_pt", paper["summary"])
                
                st.markdown(f"### [{title_pt}](https://arxiv.org/abs/{paper_id})")
                st.caption(f"👤 {paper['authors']}  |  📅 {paper['published']}  |  🏷️ {selected_cat_code}")
                st.write(summary_pt)
                
                # Sanfona para ver o original em inglês
                with st.expander("🌐 Ver original em Inglês"):
                    st.markdown(f"**{paper['title']}**")
                    st.write(paper['summary'])
                    
                st.markdown(f"📄 [Visualizar PDF completo](https://arxiv.org/pdf/{paper_id}.pdf)")
                st.divider()
                    
        except Exception as e:
            st.error(f"Erro ao conectar com o Gemini: {e}")