import sys
import subprocess
import time
import json
import urllib.request
import urllib.parse
from collections import deque
import concurrent.futures
import threading

# [라이브러리 임포트]
try:
    import tkinter as tk
    from tkinter import messagebox
    import customtkinter as ctk
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import networkx as nx
except ImportError:
    pass

# ==========================================
# [A] 백엔드 로직 (설정 및 함수들)
# ==========================================

MAX_WORKERS = 25
DRAMATIC_PAUSE = 2
BASE_URL = "https://ko.wikipedia.org/wiki/"
API_URL = "https://ko.wikipedia.org/w/api.php"
REQUIRED_PACKAGES = ["selenium", "webdriver-manager", "networkx", "customtkinter", "packaging", "matplotlib"]

def install_packages(packages, log_func):
    log_func("--- [ 0. 필수 라이브러리 확인 ] ---")
    all_success = True
    for package in packages:
        try:
            __import__(package)
            log_func(f"[OK] '{package}' 라이브러리가 확인되었습니다.")
        except ImportError:
            log_func(f"[설치] '{package}'가 없습니다. 설치를 시작합니다...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                log_func(f"[완료] '{package}' 설치 성공.")
            except subprocess.CalledProcessError:
                log_func(f"[실패] '{package}' 설치 실패.")
                all_success = False
    return all_success

def get_links_from_page(page_title):
    links = set()
    base_params = {"action": "query", "titles": page_title, "prop": "links", "plnamespace": 0, "pllimit": "max", "format": "json", "redirects": 1}
    while True:
        try:
            query_string = urllib.parse.urlencode(base_params); full_url = API_URL + "?" + query_string
            headers = {'User-Agent': 'WikiGameBot/2.0'}
            req = urllib.request.Request(full_url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response: data = json.loads(response.read().decode("utf-8"))
            page_id = next(iter(data['query']['pages']))
            if page_id == "-1" or 'links' not in data['query']['pages'][page_id]: break
            page_links = data['query']['pages'][page_id]['links']
            for link in page_links: links.add(link['title'])
            if 'continue' in data: base_params['plcontinue'] = data['continue']['plcontinue']
            else: break
        except Exception: break 
    return list(links)

def get_links_to_page(page_title):
    links = set()
    base_params = {"action": "query", "titles": page_title, "prop": "linkshere", "lhnamespace": 0, "lhlimit": "max", "format": "json", "redirects": 1}
    while True:
        try:
            query_string = urllib.parse.urlencode(base_params); full_url = API_URL + "?" + query_string
            headers = {'User-Agent': 'WikiGameBot/2.0'}
            req = urllib.request.Request(full_url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response: data = json.loads(response.read().decode("utf-8"))
            page_id = next(iter(data['query']['pages']))
            if page_id == "-1" or 'linkshere' not in data['query']['pages'][page_id]: break
            page_links = data['query']['pages'][page_id]['linkshere']
            for link in page_links: links.add(link['title'])
            if 'continue' in data: base_params['lhcontinue'] = data['continue']['lhcontinue']
            else: break
        except Exception: break
    return list(links)

def find_shortest_path(start, end, log_func):
    import networkx as nx
    G = nx.Graph()
    G.add_node(start, type='start'); G.add_node(end, type='end')
    queue_f = deque([start]); paths_f = {start: [start]}
    queue_b = deque([end]); paths_b = {end: [end]}
    
    log_func(f"🚀 양방향 병렬 탐색 시작: '{start}' <--> '{end}'")
    depth = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        while queue_f and queue_b:
            depth += 1
            log_func(f"\n--- [ {depth}단계 탐색 중... ] ---")
            
            # 정방향
            current_pages_f = list(queue_f); queue_f.clear()
            log_func(f"➡️ [1팀/정방향] {len(current_pages_f)}개 문서 동시 분석 중...")
            results_f = list(executor.map(get_links_from_page, current_pages_f))
            for i, links in enumerate(results_f):
                current_page = current_pages_f[i]; current_path = paths_f[current_page]
                for link_page in links:
                    if link_page not in G: G.add_node(link_page, type='normal')
                    G.add_edge(current_page, link_page)
                    if link_page in paths_b:
                        log_func(f"✨ 교차점 발견! : [{link_page}]")
                        G.nodes[link_page]['type'] = 'intersection'
                        path_f = current_path + [link_page]; path_b = paths_b[link_page]; path_b.reverse()
                        return path_f + path_b[1:], G
                    if link_page not in paths_f: new_path = current_path + [link_page]; paths_f[link_page] = new_path; queue_f.append(link_page)

            # 역방향
            current_pages_b = list(queue_b); queue_b.clear()
            log_func(f"⬅️ [2팀/역방향] {len(current_pages_b)}개 문서 동시 분석 중...")
            results_b = list(executor.map(get_links_to_page, current_pages_b))
            for i, links in enumerate(results_b):
                current_page = current_pages_b[i]; current_path = paths_b[current_page]
                for link_page in links:
                    if link_page not in G: G.add_node(link_page, type='normal')
                    G.add_edge(current_page, link_page)
                    if link_page in paths_f:
                        log_func(f"✨ 교차점 발견! : [{link_page}]")
                        G.nodes[link_page]['type'] = 'intersection'
                        path_f = paths_f[link_page]; path_b = current_path + [link_page]; path_b.reverse()
                        return path_f + path_b[1:], G
                    if link_page not in paths_b: new_path = current_path + [link_page]; paths_b[link_page] = new_path; queue_b.append(link_page)
            
            if depth > 4: log_func("⚠️ 탐색이 너무 깊어져 중단합니다."); return None, G
    return None, G

# 6. 셀레니움 시연 (시네마틱 줌인 & 스무스 스크롤)
def show_path_selenium(path, log_func):
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options  # [신규] 옵션 설정을 위해 필요
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.common.exceptions import NoSuchElementException, ElementNotInteractableException

    if not path: return
    log_func("\n🎬 [자동 시연] 브라우저를 전체화면으로 실행합니다...")
    
    driver = None
    try:
        # [신규] 전체화면 옵션 설정
        chrome_options = Options()
        chrome_options.add_argument("--start-fullscreen") # F11 누른 효과
        # chrome_options.add_argument("--kiosk") # (옵션) 주소창도 없는 완전 키오스크 모드 원하면 주석 해제

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.implicitly_wait(3)
        
        # 첫 페이지 이동
        driver.get(BASE_URL + path[0])
        log_func(f"📍 시작 페이지 이동: {path[0]}")
        
        for i in range(len(path) - 1):
            curr, next_p = path[i], path[i+1]
            log_func(f"🔎 '{curr}' -> '{next_p}' 찾는 중...")
            
            link = None
            
            # [링크 찾기 전략: Title -> Text -> Partial Text]
            try:
                content = driver.find_element(By.ID, "mw-content-text")
                link = content.find_element(By.CSS_SELECTOR, f"a[title='{next_p}']")
            except NoSuchElementException: pass

            if not link:
                try: link = driver.find_element(By.LINK_TEXT, next_p)
                except NoSuchElementException: pass
            
            if not link:
                try: link = driver.find_element(By.PARTIAL_LINK_TEXT, next_p)
                except NoSuchElementException: pass

            if link:
                try:
                    # ---------------------------------------------------------
                    # [연출 시작] 1. 강조 표시 (노랑 배경/빨강 테두리)
                    # ---------------------------------------------------------
                    driver.execute_script("arguments[0].style.backgroundColor='yellow'; arguments[0].style.border='3px solid red';", link)
                    
                    # ---------------------------------------------------------
                    # [연출 2] 부드러운 스크롤 (Smooth Scroll)
                    # ---------------------------------------------------------
                    # block: 'center' 옵션으로 링크가 화면 정중앙에 오도록 부드럽게 이동
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", link)
                    
                    # 스크롤이 이동하는 시간을 줘야 하므로 1.5초 대기
                    time.sleep(1.5)

                    # ---------------------------------------------------------
                    # [연출 3] 화면 줌인 (Zoom In)
                    # ---------------------------------------------------------
                    # 1. 줌 트랜지션 시간 설정 (부드럽게 확대되도록)
                    driver.execute_script("document.body.style.transition = 'transform 1.0s ease-in-out';")
                    
                    # 2. 확대 중심점을 찾은 링크의 위치로 설정
                    # (getBoundingClientRect로 좌표를 계산하여 transformOrigin 설정)
                    zoom_script = """
                    var rect = arguments[0].getBoundingClientRect();
                    var cx = rect.left + rect.width / 2;
                    var cy = rect.top + rect.height / 2;
                    document.body.style.transformOrigin = cx + 'px ' + cy + 'px';
                    document.body.style.transform = 'scale(2.0)';
                    """
                    driver.execute_script(zoom_script, link)
                    
                    log_func(f"   ✨ 발견! 줌인 효과 적용 중...")
                    time.sleep(2) # 확대된 상태로 2초간 보여줌

                    # ---------------------------------------------------------
                    # [연출 4] 줌 아웃 (원상복구) 및 이동
                    # ---------------------------------------------------------
                    # 클릭 안정성을 위해 화면 배율을 원래대로(scale 1.0) 돌려놓습니다.
                    driver.execute_script("document.body.style.transform = 'scale(1.0)';")
                    time.sleep(1.0) # 줌아웃 대기

                    # 클릭 시도
                    try: link.click()
                    except (ElementNotInteractableException, Exception):
                        driver.execute_script("arguments[0].click();", link)
                        
                except Exception as e:
                    log_func(f"❌ 발견했으나 연출/클릭 중 오류: {e}")
                    break
            else:
                log_func(f"❌ 링크를 화면에서 찾을 수 없음: {next_p}")
                break
        
        log_func("✅ 시연 완료! 10초 후 종료됩니다.")
        time.sleep(10)
        
    except Exception as e:
        log_func(f"❌ 셀레니움 오류: {e}")
    finally:
        if driver: driver.quit()
        
# ==========================================
# [B] 프론트엔드 (GUI)
# ==========================================

class ModernWikiApp:
    def __init__(self):
        ctk.set_appearance_mode("Dark") 
        ctk.set_default_color_theme("blue") 
        
        self.root = ctk.CTk()
        self.root.title("Wiki 6-Degrees Explorer")
        
        # 초기 사이즈: 튜토리얼 및 입력창용 (작음)
        self.root.geometry("450x750")
        
        # 화면 전환을 위한 메인 컨테이너
        self.main_container = ctk.CTkFrame(self.root, corner_radius=0, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True)

        # 1. 튜토리얼 화면 먼저 실행
        self.setup_tutorial_ui()

    def setup_tutorial_ui(self):
        """사용법 안내 화면 (처음 실행 시)"""
        self.clear_frame(self.main_container)

        tutorial_frame = ctk.CTkFrame(self.main_container, corner_radius=15)
        tutorial_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(tutorial_frame, text="환영합니다!", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(40, 10))
        ctk.CTkLabel(tutorial_frame, text="위키백과 6단계 법칙 탐색기", font=ctk.CTkFont(size=16), text_color="gray").pack(pady=(0, 30))

        # 설명 텍스트
        info_text = (
            "이 프로그램은 '고양이'에서 '컴퓨터'까지\n"
            "링크를 타고 이동하는 최단 경로를 찾아줍니다.\n\n"
            "1️⃣ [설정] 시작 문서와 목표 문서를 입력하세요.\n"
            "2️⃣ [탐색] AI가 양방향으로 길을 찾습니다.\n"
            "3️⃣ [시각화] 탐색된 경로를 그래프로 보여줍니다.\n"
            "4️⃣ [시연] 실제 브라우저가 자동으로 클릭합니다."
        )
        info_label = ctk.CTkLabel(tutorial_frame, text=info_text, font=ctk.CTkFont(size=14), justify="left", height=200)
        info_label.pack(pady=20, padx=20)

        start_btn = ctk.CTkButton(tutorial_frame, text="시작하기", height=50, font=ctk.CTkFont(size=16, weight="bold"),
                                  command=self.setup_main_ui)
        start_btn.pack(pady=30, padx=40, fill="x")

    def setup_main_ui(self):
        """메인 프로그램 화면 (입력창 + 로그)"""
        self.clear_frame(self.main_container)
        
        # --- [왼쪽 패널: 컨트롤 & 로그] ---
        # 처음에는 화면을 꽉 채우게 설정
        self.left_panel = ctk.CTkFrame(self.main_container, corner_radius=0)
        self.left_panel.pack(side="left", fill="both", expand=True)
        
        # 타이틀
        ctk.CTkLabel(self.left_panel, text="경로 탐색기", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(20, 10), padx=20, anchor="w")

        # 입력 영역
        input_frame = ctk.CTkFrame(self.left_panel)
        input_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(input_frame, text="시작 문서:").pack(anchor="w", padx=10, pady=(10,0))
        self.entry_start = ctk.CTkEntry(input_frame)
        self.entry_start.insert(0, "고양이")
        self.entry_start.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(input_frame, text="목표 문서:").pack(anchor="w", padx=10)
        self.entry_end = ctk.CTkEntry(input_frame)
        self.entry_end.insert(0, "컴퓨터")
        self.entry_end.pack(fill="x", padx=10, pady=(0, 10))

        self.btn_run = ctk.CTkButton(input_frame, text="탐색 시작", command=self.start_process, fg_color="#007bff")
        self.btn_run.pack(fill="x", padx=10, pady=10)

        # 로그 영역
        ctk.CTkLabel(self.left_panel, text="실행 로그", font=ctk.CTkFont(size=12, weight="bold")).pack(pady=(20, 5), padx=20, anchor="w")
        self.log_area = ctk.CTkTextbox(self.left_panel, font=("Consolas", 11))
        self.log_area.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.log_area.configure(state="disabled")

        # --- [오른쪽 패널: 그래프 (처음에는 숨김)] ---
        # pack하지 않고 변수만 만들어둠
        self.right_panel = ctk.CTkFrame(self.main_container, corner_radius=0, fg_color="#2b2b2b")
        self.canvas_frame = ctk.CTkFrame(self.right_panel, fg_color="#2b2b2b")
        self.canvas_frame.pack(fill="both", expand=True, padx=10, pady=10)

    def show_graph_panel(self):
        """그래프 패널을 활성화하고 창을 넓히는 함수"""
        # 이미 열려있지 않다면
        if not self.right_panel.winfo_ismapped():
            # 윈도우 크기 확장 (애니메이션 효과처럼 보임)
            current_x = self.root.winfo_x()
            current_y = self.root.winfo_y()
            self.root.geometry(f"1100x750+{current_x}+{current_y}")
            
            # 오른쪽 패널 붙이기
            self.right_panel.pack(side="right", fill="both", expand=True)
            
            # 왼쪽 패널 비율 조정 (좁게)
            self.left_panel.pack_configure(expand=False, fill="y", ipadx=0)
            self.left_panel.configure(width=350)

    def clear_frame(self, frame):
        for widget in frame.winfo_children():
            widget.destroy()

    def log(self, message):
        self.log_area.configure(state="normal")
        self.log_area.insert("end", message + "\n")
        self.log_area.see("end")
        self.log_area.configure(state="disabled")

    def start_process(self):
        start = self.entry_start.get().strip()
        end = self.entry_end.get().strip()

        if not start or not end:
            tk.messagebox.showwarning("입력 오류", "문서를 모두 입력해주세요.")
            return

        self.btn_run.configure(state="disabled", text="탐색 중...")
        self.log_area.configure(state="normal")
        self.log_area.delete("1.0", "end")
        self.log_area.configure(state="disabled")
        
        # 이전 그래프 지우기
        for widget in self.canvas_frame.winfo_children():
            widget.destroy()

        thread = threading.Thread(target=self.run_logic, args=(start, end))
        thread.daemon = True
        thread.start()

    def run_logic(self, start, end):
        pkgs = [p for p in REQUIRED_PACKAGES if p != "customtkinter" and p != "matplotlib"]
        if not install_packages(pkgs, self.log):
            self.log("❌ 필수 패키지 설치 실패.")
            self.reset_button()
            return

        start_time = time.time()
        path, G = find_shortest_path(start, end, self.log)
        
        if path:
            duration = time.time() - start_time
            self.log(f"\n✅ 경로 발견! ({len(path)-1}단계, {duration:.2f}초)")
            self.log(f"🔗 {' -> '.join(path)}")
            
            # [수정] 성공 시에만 그래프 패널을 열고 그리기
            # 메인 스레드에서 UI 업데이트
            self.root.after(0, lambda: self.reveal_and_draw_graph(G, path))
            
            show_path_selenium(path, self.log)
        else:
            self.log("\n❌ 경로를 찾지 못했습니다.")
            
        self.reset_button()

    def reveal_and_draw_graph(self, G, path):
        """창을 넓히고 그래프를 그리는 함수"""
        self.show_graph_panel() # 패널 열기
        self.draw_graph_in_gui(G, path) # 그리기

    def draw_graph_in_gui(self, G, path):
        import matplotlib.pyplot as plt
        import networkx as nx
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        # 그래프 그리기 로직 (이전과 동일)
        fig, ax = plt.subplots(figsize=(5, 4), facecolor='#2b2b2b')
        ax.set_axis_off()
        pos = nx.spring_layout(G, k=0.5, iterations=50)

        node_colors = []
        node_sizes = []
        path_set = set(path)
        
        for node in G.nodes():
            if node in path_set:
                node_colors.append('#f1c40f')
                node_sizes.append(300)
            elif G.nodes[node].get('type') == 'start':
                node_colors.append('#3498db')
                node_sizes.append(200)
            elif G.nodes[node].get('type') == 'end':
                node_colors.append('#e74c3c')
                node_sizes.append(200)
            else:
                node_colors.append('#95a5a6')
                node_sizes.append(50)

        nx.draw_networkx_edges(G, pos, ax=ax, edge_color='#ecf0f1', alpha=0.3)
        nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors, node_size=node_sizes)
        
        path_edges = list(zip(path, path[1:]))
        nx.draw_networkx_edges(G, pos, ax=ax, edgelist=path_edges, edge_color='#f1c40f', width=2)
        
        labels = {node: node for node in G.nodes() if node in path_set or node == path[0] or node == path[-1]}
        nx.draw_networkx_labels(G, pos, labels, ax=ax, font_size=8, font_color='white', font_family='Malgun Gothic')

        canvas = FigureCanvasTkAgg(fig, master=self.canvas_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def reset_button(self):
        self.root.after(0, lambda: self.btn_run.configure(state="normal", text="탐색 시작"))

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    try:
        import customtkinter
        import matplotlib
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter", "matplotlib"])
        import customtkinter
    
    app = ModernWikiApp()
    app.run()