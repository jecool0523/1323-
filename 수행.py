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
    
    # [Matplotlib 안전한 임포트]
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk # 툴바 추가
    import networkx as nx
except ImportError:
    pass

# ==========================================
# [A] 백엔드 로직
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
    G.add_node(start, type='start', level=0)
    G.add_node(end, type='end', level=99) # 목표는 잠시 멀리 둠

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
                    if link_page not in G: G.add_node(link_page, type='normal', level=depth)
                    G.add_edge(current_page, link_page)
                    if link_page in paths_b:
                        log_func(f"✨ 교차점 발견! : [{link_page}]")
                        G.nodes[link_page]['type'] = 'intersection'
                        G.nodes[link_page]['level'] = depth # 교차점 레벨 설정
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
                    if link_page not in G: G.add_node(link_page, type='normal', level=depth) # 역방향도 편의상 같은 depth로 표기
                    G.add_edge(current_page, link_page)
                    if link_page in paths_f:
                        log_func(f"✨ 교차점 발견! : [{link_page}]")
                        G.nodes[link_page]['type'] = 'intersection'
                        path_f = paths_f[link_page]; path_b = current_path + [link_page]; path_b.reverse()
                        return path_f + path_b[1:], G
                    if link_page not in paths_b: new_path = current_path + [link_page]; paths_b[link_page] = new_path; queue_b.append(link_page)
            
            if depth > 4: log_func("⚠️ 탐색이 너무 깊어져 중단합니다."); return None, G
    return None, G

# 6. 셀레니움 시연 (좌표 오차 수정 버전)
def show_path_selenium(path, log_func):
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.common.exceptions import NoSuchElementException, ElementNotInteractableException

    if not path: return
    log_func("\n🎬 [자동 시연] 브라우저를 전체화면으로 실행합니다...")
    driver = None
    try:
        # SSL 오류 방지
        import os
        os.environ['WDM_SSL_VERIFY'] = '0'
        
        chrome_options = Options()
        chrome_options.add_argument("--start-fullscreen")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.implicitly_wait(3)
        
        driver.get(BASE_URL + path[0])
        log_func(f"📍 시작 페이지 이동: {path[0]}")
        
        for i in range(len(path) - 1):
            curr, next_p = path[i], path[i+1]
            log_func(f"🔎 '{curr}' -> '{next_p}' 찾는 중...")
            link = None
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
                    # 1. 강조 효과 (노랑 배경 + 빨강 테두리)
                    driver.execute_script("arguments[0].style.backgroundColor='yellow'; arguments[0].style.border='3px solid red';", link)
                    
                    # 2. 부드러운 스크롤 (화면 중앙으로)
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", link)
                    time.sleep(1.5) # 스크롤 이동 대기
                    
                    # 3. [핵심 수정] 좌표 계산에 '스크롤 위치(window.scrollX/Y)'를 더함
                    driver.execute_script("document.body.style.transition = 'transform 1.0s ease-in-out';")
                    zoom_script = """
                    var element = arguments[0];
                    var rect = element.getBoundingClientRect();
                    
                    // [수정된 공식]
                    // 요소의 화면상 좌표(rect) + 현재 스크롤된 거리(window.scroll) = 문서 전체 기준 절대 좌표
                    var cx = rect.left + window.scrollX + (rect.width / 2);
                    var cy = rect.top + window.scrollY + (rect.height / 2);
                    
                    document.body.style.transformOrigin = cx + 'px ' + cy + 'px';
                    document.body.style.transform = 'scale(2.0)';
                    """
                    driver.execute_script(zoom_script, link)
                    log_func(f"   ✨ 발견! 정확한 위치로 줌인...")
                    time.sleep(2)

                    # 4. 줌 아웃 (원상복구)
                    driver.execute_script("document.body.style.transform = 'scale(1.0)';")
                    time.sleep(1.0)

                    # 5. 클릭
                    try: link.click()
                    except (ElementNotInteractableException, Exception):
                        driver.execute_script("arguments[0].click();", link)
                except Exception as e: log_func(f"❌ 발견했으나 연출/클릭 중 오류: {e}"); break
            else: log_func(f"❌ 링크를 화면에서 찾을 수 없음: {next_p}"); break
        
        log_func("✅ 시연 완료! 10초 후 종료됩니다."); time.sleep(10)
    except Exception as e: log_func(f"❌ 셀레니움 오류: {e}")
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
        self.root.geometry("450x750")
        
        self.main_container = ctk.CTkFrame(self.root, corner_radius=0, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True)

        self.setup_tutorial_ui()

    def setup_tutorial_ui(self):
        self.clear_frame(self.main_container)
        tutorial_frame = ctk.CTkFrame(self.main_container, corner_radius=15)
        tutorial_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(tutorial_frame, text="환영합니다!", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(40, 10))
        ctk.CTkLabel(tutorial_frame, text="위키백과 6단계 법칙 탐색기", font=ctk.CTkFont(size=16), text_color="gray").pack(pady=(0, 30))

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
        self.clear_frame(self.main_container)
        
        self.left_panel = ctk.CTkFrame(self.main_container, corner_radius=0)
        self.left_panel.pack(side="left", fill="both", expand=True)
        
        ctk.CTkLabel(self.left_panel, text="경로 탐색기", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(20, 10), padx=20, anchor="w")

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

        ctk.CTkLabel(self.left_panel, text="실행 로그", font=ctk.CTkFont(size=12, weight="bold")).pack(pady=(20, 5), padx=20, anchor="w")
        self.log_area = ctk.CTkTextbox(self.left_panel, font=("Consolas", 11))
        self.log_area.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.log_area.configure(state="disabled")

        self.right_panel = ctk.CTkFrame(self.main_container, corner_radius=0, fg_color="#2b2b2b")
        # 툴바를 위한 프레임 추가
        self.toolbar_frame = ctk.CTkFrame(self.right_panel, fg_color="#2b2b2b", height=40)
        self.toolbar_frame.pack(side="bottom", fill="x")
        self.canvas_frame = ctk.CTkFrame(self.right_panel, fg_color="#2b2b2b")
        self.canvas_frame.pack(fill="both", expand=True, padx=10, pady=10)

    def show_graph_panel(self):
        if not self.right_panel.winfo_ismapped():
            current_x = self.root.winfo_x()
            current_y = self.root.winfo_y()
            self.root.geometry(f"1200x800+{current_x}+{current_y}") # 사이즈 좀 더 키움
            self.right_panel.pack(side="right", fill="both", expand=True)
            self.left_panel.pack_configure(expand=False, fill="y", ipadx=0)
            self.left_panel.configure(width=350)

    def clear_frame(self, frame):
        for widget in frame.winfo_children():
            widget.destroy()

    def log(self, message):
        self.root.after(0, lambda: self._log_impl(message))

    def _log_impl(self, message):
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
        
        # 이전 그래프/툴바 지우기
        for widget in self.canvas_frame.winfo_children(): widget.destroy()
        for widget in self.toolbar_frame.winfo_children(): widget.destroy()

        thread = threading.Thread(target=self.run_logic, args=(start, end))
        thread.daemon = True
        thread.start()

    def run_logic(self, start, end):
        pkgs = [p for p in REQUIRED_PACKAGES if p != "customtkinter" and p != "matplotlib"]
        if not install_packages(pkgs, self.log):
            self.log("❌ 필수 패키지 설치 실패.")
            self.reset_button(); return

        start_time = time.time()
        path, G = find_shortest_path(start, end, self.log)
        
        if path:
            duration = time.time() - start_time
            self.log(f"\n✅ 경로 발견! ({len(path)-1}단계, {duration:.2f}초)")
            self.log(f"🔗 {' -> '.join(path)}")
            
            self.log("📊 그래프 배치 계산 중 (왼쪽:시작 -> 오른쪽:목표)...")
            import networkx as nx
            try:
                # [개선] 시작은 왼쪽, 목표는 오른쪽으로 고정하여 방향성 부여
                fixed_pos = {start: (-1, 0), end: (1, 0)}
                # k값을 키워(1.5) 노드 간격을 넓힘
                pos = nx.spring_layout(G, k=1.5, pos=fixed_pos, fixed=[start, end], seed=42)
                self.root.after(0, lambda: self.reveal_and_draw_graph(G, path, pos))
            except Exception as e:
                self.log(f"❌ 그래프 계산 오류: {e}")
            
            show_path_selenium(path, self.log)
        else:
            self.log("\n❌ 경로를 찾지 못했습니다.")
            
        self.reset_button()

    def reveal_and_draw_graph(self, G, path, pos):
        self.show_graph_panel()
        self.draw_graph_in_gui(G, path, pos)

    def draw_graph_in_gui(self, G, path, pos):
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        import networkx as nx

        # 1. Figure 생성
        fig = Figure(figsize=(5, 4), facecolor='#2b2b2b')
        ax = fig.add_subplot(111)
        ax.set_axis_off()

        # 2. 스타일링
        node_colors = []
        node_sizes = []
        node_alphas = []
        path_set = set(path)
        
        for node in G.nodes():
            if node in path_set:
                node_colors.append('#f1c40f') # 경로: 밝은 노랑
                node_sizes.append(400)       # 크기: 큼
                node_alphas.append(1.0)      # 투명도: 불투명
            elif G.nodes[node].get('type') == 'start':
                node_colors.append('#3498db')
                node_sizes.append(300)
                node_alphas.append(1.0)
            elif G.nodes[node].get('type') == 'end':
                node_colors.append('#e74c3c')
                node_sizes.append(300)
                node_alphas.append(1.0)
            else:
                node_colors.append('#95a5a6') # 기타: 회색
                node_sizes.append(50)        # 크기: 작음
                node_alphas.append(0.3)      # 투명도: 흐릿함

        # 3. 그리기 (비경로 요소 먼저 -> 경로 요소 나중에)
        # 3-1. 흐릿한 엣지 먼저
        nx.draw_networkx_edges(G, pos, ax=ax, edge_color='#ecf0f1', alpha=0.1, width=0.5)
        # 3-2. 흐릿한 노드
        nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors, node_size=node_sizes, alpha=0.3)
        
        # 3-3. 정답 경로 강조 (맨 위에 덧그리기)
        path_edges = list(zip(path, path[1:]))
        # 경로 노드만 다시 그리기 (불투명하게)
        path_nodes = list(path_set)
        nx.draw_networkx_nodes(G, pos, ax=ax, nodelist=path_nodes, node_color='#f1c40f', node_size=400, label="Path")
        # 경로 엣지 다시 그리기 (두껍게)
        nx.draw_networkx_edges(G, pos, ax=ax, edgelist=path_edges, edge_color='#f1c40f', width=3.0)
        
        # 4. 라벨 (경로 노드만 표시)
        labels = {node: node for node in G.nodes() if node in path_set}
        # 폰트는 깨짐 방지를 위해 영어 폰트나 시스템 폰트 사용 (한글이 깨질 경우 Malgun Gothic 등 지정)
        nx.draw_networkx_labels(G, pos, labels, ax=ax, font_size=9, font_color='white', font_weight='bold', font_family='Malgun Gothic')

        # 5. 캔버스 배치
        canvas = FigureCanvasTkAgg(fig, master=self.canvas_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        # 6. [핵심] 툴바 추가 (줌/이동 가능)
        toolbar = NavigationToolbar2Tk(canvas, self.toolbar_frame)
        toolbar.update()
        toolbar.pack(side="bottom", fill="x")

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
