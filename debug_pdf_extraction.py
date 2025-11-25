import requests
from bs4 import BeautifulSoup
import io
from pypdf import PdfReader
import re
import unicodedata
from pncp_client import PNCPClient

def debug_femurn():
    with open("debug_results.txt", "w", encoding="utf-8") as log:
        def log_print(msg):
            print(msg)
            log.write(msg + "\n")

        log_print("🔍 DEBUGGING FEMURN PDF EXTRACTION")
        base_url = "https://www.diariomunicipal.com.br/femurn/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        # 1. Get PDF URL
        log_print("1. Fetching Homepage...")
        try:
            response = requests.get(base_url, headers=headers, timeout=15, verify=False)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            pdf_url = None
            link_tag = soup.find('a', id='downloadPdf')
            if link_tag: pdf_url = link_tag.get('href')
            
            if not pdf_url:
                input_tag = soup.find('input', id='urlPdf')
                if input_tag: pdf_url = input_tag.get('value')
                
            if not pdf_url:
                log_print("❌ Could not find PDF URL on homepage.")
                return

            log_print(f"✅ Found PDF URL: {pdf_url}")

            # 2. Download PDF
            log_print("2. Downloading PDF...")
            pdf_response = requests.get(pdf_url, headers=headers, timeout=60, verify=False)
            log_print(f"✅ Downloaded ({len(pdf_response.content)} bytes)")

            # 3. Extract Text
            log_print("3. Extracting Text...")
            f = io.BytesIO(pdf_response.content)
            reader = PdfReader(f)
            text = ""
            for i, page in enumerate(reader.pages):
                text += page.extract_text() + "\n"
                if i == 0:
                    log_print(f"--- Page 1 Preview ---\n{page.extract_text()[:500]}\n----------------------")
            
            log_print(f"✅ Total Text Length: {len(text)} chars")

            # 4. Check Delimiter
            log_print("4. Checking Delimiters...")
            delimiters = [
                "Código Identificador:",
                "Código Identificador :",
                "Codigo Identificador:",
                "CÓDIGO IDENTIFICADOR:",
                "Código Identificador"
            ]
            
            found_delim = False
            for d in delimiters:
                if d in text:
                    log_print(f"✅ Delimiter '{d}' FOUND in text.")
                    found_delim = True
                    chunks = re.split(re.escape(d) + r'\s*[\w\d]+', text)
                    log_print(f"   -> Split into {len(chunks)} chunks.")
                    break
            
            if not found_delim:
                log_print("❌ No known delimiter found in text.")
                log_print("   -> Splitting logic will FAIL.")
                log_print("   -> First 500 chars of text for inspection:")
                log_print(text[:500])

            # 5. Simulate Scraper Logic
            log_print("5. Simulating Scraper Logic...")
            
            client = PNCPClient()
            # Prepare Regex
            termos_busca = client.TERMOS_POSITIVOS_PADRAO
            termos_negativos = client.TERMOS_NEGATIVOS_PADRAO
            
            def normalize(t):
                return unicodedata.normalize('NFKD', t).encode('ASCII', 'ignore').decode('ASCII').upper()

            terms_to_search_norm = [normalize(t) for t in termos_busca if t and t.strip()]
            terms_negativos_norm = [normalize(t) for t in termos_negativos]
            
            terms_to_search_norm.sort(key=len, reverse=True)
            terms_negativos_norm.sort(key=len, reverse=True)
            
            positive_pattern = re.compile(r'\b(?:' + '|'.join(map(re.escape, terms_to_search_norm)) + r')\b')
            negative_pattern = re.compile(r'\b(?:' + '|'.join(map(re.escape, terms_negativos_norm)) + r')\b')
            
            # Split
            chunks = re.split(r'(Código Identificador:\s*[\w\d]+)', text)
            
            valid_count = 0
            rejected_neg = 0
            rejected_no_match = 0
            
            for i in range(0, len(chunks)-1, 2):
                body = chunks[i]
                code = chunks[i+1]
                full_notice = body + "\n" + code
                full_notice_clean = re.sub(r'\n+', '\n', full_notice).strip()
                full_notice_norm = normalize(full_notice_clean)
                
                # Check Positive
                pos_match = positive_pattern.search(full_notice_norm)
                if pos_match:
                    # Check Negative
                    neg_match = negative_pattern.search(full_notice_norm)
                    if neg_match:
                        rejected_neg += 1
                        if rejected_neg <= 3:
                            log_print(f"❌ Rejected by Negative Term '{neg_match.group(0)}': {full_notice_clean[:100]}...")
                    else:
                        # Check Already Hired (Skip Patterns)
                        skip_patterns = [
                            r'CONTRATAD[OA]\s*:\s*[A-Z]',
                            r'CONTRATAD[OA]\s*\([Aa]\)\s*:\s*[A-Z]',
                            r'VENCEDOR\s*:\s*[A-Z]',
                            r'EMPRESA\s+VENCEDORA\s*:\s*[A-Z]',
                        ]
                        should_skip = False
                        skip_reason = ""
                        for skip_pat in skip_patterns:
                            if re.search(skip_pat, full_notice_clean, re.IGNORECASE):
                                should_skip = True
                                skip_reason = skip_pat
                                break
                        
                        if should_skip:
                            log_print(f"❌ Rejected by 'Already Hired' Pattern '{skip_reason}': {full_notice_clean[:100]}...")
                        else:
                            valid_count += 1
                            if valid_count <= 5:
                                log_print(f"✅ ACCEPTED: {full_notice_clean[:100]}...")
                                log_print(f"   Match: {pos_match.group(0)}")
                else:
                    rejected_no_match += 1
            
            log_print(f"\n📊 Simulation Results:")
            log_print(f"   Total Chunks: {len(chunks)//2}")
            log_print(f"   Accepted: {valid_count}")
            log_print(f"   Rejected (Negative): {rejected_neg}")
            log_print(f"   Rejected (No Match): {rejected_no_match}")

        except Exception as e:
            log_print(f"❌ Error: {e}")

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings()
    debug_femurn()
