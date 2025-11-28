# 임포트 쭉
import sys
import subprocess
import time
import json
import urllib.request
import urllib.parse
from collections import deque
import concurrent.futures
import threading
import random
try:
    import tkinter as tk
    from tkinter import messagebox
    import customtkinter as ctk  #GUI 새로운거 안되면 위에걸로 기본 UI 만들기
    
    import matplotlib 
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    import networkx as nx
except ImportError:
    pass

# ==============
# 내부 탐색 & 시연
# ==============


# 중요 변수
THREADS = 25
DELAY = 2

WIKI = "https://ko.wikipedia.org/wiki/"   # 기본 페이지
API = "https://ko.wikipedia.org/w/api.php"    # api 키
PACKAGES = ["selenium", "webdriver-manager", "networkx", "customtkinter", "packaging", "matplotlib"]


# 라이브러리 다운 
def install_packages(packages, log_func):
    log_func("--- [ 0. 필수 라이브러리 확인 ] ---")
    success = True
    for package in packages:
        try:
            __import__(package)
            log_func(f"[OK] '{package}' 라이브러리 확인")
        except ImportError:
            log_func(f"[설치] '{package}'가 없습니다. 설치 시작")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                log_func(f"[완료] '{package}' 설치 성공.")
            except subprocess.CalledProcessError:
                log_func(f"[실패] '{package}' 설치 실패.")
                success = False
    return success

# 페이지 링크 가져오기 by. wiki
def get_links_from_page(page_title):
    links = set()
    WIKI_params = {"action": "query", "titles": page_title, "prop": "links", "plnamespace": 0, "pllimit": "max", "format": "json", "redirects": 1}
    while True:
        try:
            query_string = urllib.parse.urlencode(WIKI_params); full_url = API + "?" + query_string
            headers = {'User-Agent': 'WikiGameBot/2.0'}
            req = urllib.request.Request(full_url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response: data = json.loads(response.read().decode("utf-8"))
            page_id = next(iter(data['query']['pages']))
            if page_id == "-1" or 'links' not in data['query']['pages'][page_id]: break
            page_links = data['query']['pages'][page_id]['links']
            for link in page_links: links.add(link['title'])
            if 'continue' in data: WIKI_params['plcontinue'] = data['continue']['plcontinue']
            else: break
        except Exception: break 
    return list(links)

def get_links_to_page(page_title):
    links = set()
    WIKI_params = {"action": "query", "titles": page_title, "prop": "linkshere", "lhnamespace": 0, "lhlimit": "max", "format": "json", "redirects": 1}
    while True:
        try:
            query_string = urllib.parse.urlencode(WIKI_params); full_url = API + "?" + query_string
            headers = {'User-Agent': 'WikiGameBot/2.0'}
            req = urllib.request.Request(full_url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response: data = json.loads(response.read().decode("utf-8"))
            page_id = next(iter(data['query']['pages']))
            if page_id == "-1" or 'linkshere' not in data['query']['pages'][page_id]: break
            page_links = data['query']['pages'][page_id]['linkshere']
            for link in page_links: links.add(link['title'])
            if 'continue' in data: WIKI_params['lhcontinue'] = data['continue']['lhcontinue']
            else: break
        except Exception: break
    return list(links)

# 1 양방향 탐색 -  기본

def find_shortest_path(start, end, log_func):
    import networkx as nx
    G = nx.Graph()
    G.add_node(start, type='start')
    G.add_node(end, type='end')

    queue_f = deque([start]); paths_f = {start: [start]}
    queue_b = deque([end]); paths_b = {end: [end]}
    
    log_func(f" [1차] 양방향 병렬 탐색 시작: '{start}' <--> '{end}'")
    depth = 0
    with concurrent.futures.ThreadPoolExecutor(THREADS=THREADS) as executor:
        while queue_f and queue_b:
            depth += 1
            log_func(f"\n--- [ Depth {depth} ] ---")
            
            # 정방향
            current_pages_f = list(queue_f); queue_f.clear()
            log_func(f"-> [1팀/정방향] {len(current_pages_f)}개 문서 분석...")
            results_f = list(executor.map(get_links_from_page, current_pages_f))
            for i, links in enumerate(results_f):
                current_page = current_pages_f[i]; current_path = paths_f[current_page]
                for link_page in links:
                    if link_page not in G: G.add_node(link_page, type='normal')
                    G.add_edge(current_page, link_page)
                    if link_page in paths_b:
                        log_func(f" ! 교차점 발견 : [{link_page}]")
                        G.nodes[link_page]['type'] = 'intersection'
                        path_f = current_path + [link_page]; path_b = paths_b[link_page]; path_b.reverse()
                        return path_f + path_b[1:], G
                    if link_page not in paths_f: new_path = current_path + [link_page]; paths_f[link_page] = new_path; queue_f.append(link_page)

            # 역방향
            current_pages_b = list(queue_b); queue_b.clear()
            log_func(f"<- [2팀/역방향] {len(current_pages_b)}개 문서 분석...")
            results_b = list(executor.map(get_links_to_page, current_pages_b))
            for i, links in enumerate(results_b):      # 이거 왜 안됌?
                current_page = current_pages_b[i]; current_path = paths_b[current_page]
                for link_page in links:
                    if link_page not in G: G.add_node(link_page, type='normal')
                    G.add_edge(current_page, link_page)
                    if link_page in paths_f:    # 이거 맞지않나
                        log_func(f" ! 교차점 발견 : [{link_page}]")
                        G.nodes[link_page]['type'] = 'intersection'
                        path_f = paths_f[link_page]; path_b = current_path + [link_page]; path_b.reverse()
                        return path_f + path_b[1:], G
                    if link_page not in paths_b: new_path = current_path + [link_page]; paths_b[link_page] = new_path; queue_b.append(link_page)
            
            if depth > 4: log_func(" 탐색이 너무 깊어져 중단합니다."); return None, G
    return None, G

# [2] 정방향 전용 탐색
# 안되면 한번 더 하기 

def find_shortest_path_forward_only(start, end, log_func):
    import networkx as nx
    G = nx.Graph()
    G.add_node(start, type='start')
    G.add_node(end, type='end')

    queue = deque([start])
    visited = {start: [start]}
    
    log_func(f" [2차] 정방향 안전 탐색 시작: '{start}' -> '{end}'")
    depth = 0
    
    with concurrent.futures.ThreadPoolExecutor(THREADS=THREADS) as executor:
        while queue:
            depth += 1
            log_func(f"\n--- [ Depth {depth} (Forward) ] ---")
            
            current_pages = list(queue)
            queue.clear()
            
            log_func(f"-> {len(current_pages)}개 문서 분석 중...")
            results = list(executor.map(get_links_from_page, current_pages))
            
            for i, links in enumerate(results):
                parent = current_pages[i]
                current_path = visited[parent]
                
                for link in links:
                    if link not in G: G.add_node(link, type='normal')
                    G.add_edge(parent, link)
                    
                    if link == end:
                        log_func(f" ! 목표 발견 : [{link}]")
                        return current_path + [link], G
                    
                    if link not in visited:
                        visited[link] = current_path + [link]
                        queue.append(link)
            
            if depth > 5:
                log_func(" # 탐색이 너무 깊어져 중단합니다.")
                return None, G
    return None, G

# 셀레니움 시연 함수
def show_path_selenium(path, log_func):
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.common.exceptions import NoSuchElementException, ElementNotInteractableException

    if not path: return False # 실패 반환
    
    log_func("\n [자동 시연] 브라우저를 전체화면으로 실행합니다...")
    driver = None
    success = False # 성공 여부 추적

    try:
        import os
        os.environ['WDM_SSL_VERIFY'] = '0'
        
        chrome_options = Options()
        chrome_options.add_argument("--start-fullscreen")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.implicitly_wait(3)
        
        driver.get(WIKI + path[0])
        log_func(f" 시작 페이지 이동: {path[0]}")
        
        for i in range(len(path) - 1):
            curr, next_p = path[i], path[i+1]
            log_func(f" '{curr}' -> '{next_p}' 찾는 중...")
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
                    driver.execute_script("arguments[0].style.backgroundColor='yellow'; arguments[0].style.border='3px solid red';", link)
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", link)
                    time.sleep(1.5)
                    
                    driver.execute_script("document.body.style.transition = 'transform 1.0s ease-in-out';")
                    zoom_script = """
                    var element = arguments[0];
                    var rect = element.getBoundingClientRect();
                    var cx = rect.left + window.scrollX + (rect.width / 2);
                    var cy = rect.top + window.scrollY + (rect.height / 2);
                    document.body.style.transformOrigin = cx + 'px ' + cy + 'px';
                    document.body.style.transform = 'scale(2.0)';
                    """
                    driver.execute_script(zoom_script, link)
                    log_func(f"   !  발견 강조 효과")
                    time.sleep(2)

                    driver.execute_script("document.body.style.transform = 'scale(1.0)';")
                    time.sleep(1.0)

                    try: link.click()
                    except (ElementNotInteractableException, Exception):
                        driver.execute_script("arguments[0].click();", link)
                except Exception as e: 
                    log_func(f" 발견 but 클릭 오류: {e}")
                    success = False
                    break
            else: 
                log_func(f"# 링크를 화면에서 찾을 수 없음: {next_p}")
                success = False # 실패 기록
                break
        else:
            # for문이 break 없이 끝나면 성공
            log_func("V 시연 완료! 10초 후 종료됩니다.")
            success = True
            time.sleep(10)

    except Exception as e: 
        log_func(f"# 셀레니움 오류: {e}")   # 와이파이 이슈일수 있음.
        success = False
    finally:
        if driver: driver.quit()
        
    return success # 성공/실패 여부 반환

# =========
# [B] GUI 화ㅏ면
# =========

class ModernWikiApp:
    def __init__(self):
        ctk.set_appearance_mode("Dark") 
        ctk.set_default_color_theme("blue") 
        
        self.root = ctk.CTk()
        self.root.title("Wiki 6-Degrees Explorer")
        self.root.geometry("450x750")
        
        self.main_container = ctk.CTkFrame(self.root, corner_radius=0, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True)
        
        self.spinner_running = False
        self.setup_tutorial_ui()

    def setup_tutorial_ui(self):
        self.clear_frame(self.main_container)
        tutorial_frame = ctk.CTkFrame(self.main_container, corner_radius=15)
        tutorial_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(tutorial_frame, text="1323 제시원", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(40, 10))
        ctk.CTkLabel(tutorial_frame, text="위키백과 6단계 법칙 탐색기", font=ctk.CTkFont(size=16), text_color="gray").pack(pady=(0, 30))

        info_text = (
            "이 프로그램은 위키백과에 있는 모든 문서가\n"
            "어떻게 연결되어있는지 확인할 수 있습니다.  :) \n\n"
            " 1) [설정] 시작 문서와 목표 문서를 입력하세요.\n\t 예시) 태평양 전쟁 -> 부동소수점\n\t    루크 스카이워커 -> 한국디지털미디어고등학교\n"
            " 2) [탐색] 알고리즘이 문서 경로를 탐색하고, \n"
            " 3) [시각화] 그래프로 시각화한 후 \n"
            " 4) [시연] 실제 브라우저가 경로를 실제로 보여줍니다."
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
        self.entry_start.insert(0, "한국디지털미디어고등학교")
        self.entry_start.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(input_frame, text="목표 문서:").pack(anchor="w", padx=10)
        self.entry_end = ctk.CTkEntry(input_frame)
        self.entry_end.insert(0, "에이브러햄 링컨")
        self.entry_end.pack(fill="x", padx=10, pady=(0, 10))

        self.btn_run = ctk.CTkButton(input_frame, text="탐색 시작", command=self.start_process, fg_color="#007bff")
        self.btn_run.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(self.left_panel, text="실행 로그", font=ctk.CTkFont(size=12, weight="bold")).pack(pady=(20, 5), padx=20, anchor="w")
        self.log_area = ctk.CTkTextbox(self.left_panel, font=("Consolas", 11))
        self.log_area.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.log_area.configure(state="disabled")

        self.right_panel = ctk.CTkFrame(self.main_container, corner_radius=0, fg_color="#2b2b2b")
        self.toolbar_frame = ctk.CTkFrame(self.right_panel, fg_color="#2b2b2b", height=40)
        self.toolbar_frame.pack(side="bottom", fill="x")
        self.canvas_frame = ctk.CTkFrame(self.right_panel, fg_color="#2b2b2b")
        self.canvas_frame.pack(fill="both", expand=True, padx=10, pady=10)

    def show_graph_panel(self):
        if not self.right_panel.winfo_ismapped():
            current_x = self.root.winfo_x()
            current_y = self.root.winfo_y()
            self.root.geometry(f"1200x800+{current_x}+{current_y}")
            self.right_panel.pack(side="right", fill="both", expand=True)
            self.left_panel.pack_configure(expand=False, fill="y", ipadx=0)
            self.left_panel.configure(width=350)

    def clear_frame(self, frame):
        for widget in frame.winfo_children(): widget.destroy()

    def log(self, message):
        self.root.after(0, lambda: self._log_impl(message))

    def _log_impl(self, message):
        self.log_area.configure(state="normal")
        self.log_area.insert("end", message + "\n")
        self.log_area.see("end")
        self.log_area.configure(state="disabled")

    def start_spinner(self, message):
        self.spinner_running = True
        self.log(message)
        thread = threading.Thread(target=self._spinner_loop)
        thread.daemon = True
        thread.start()

    def stop_spinner(self):
        self.spinner_running = False

    def _spinner_loop(self):
        chars = ["|", "/", "-", "\\"]
        idx = 0
        while self.spinner_running:
            char = chars[idx % 4]
            self.root.after(0, lambda c=char: self._update_spinner_char(c))
            idx += 1
            time.sleep(0.1)
        self.root.after(0, lambda: self._update_spinner_char(" "))

    def _update_spinner_char(self, char):
        self.log_area.configure(state="normal")
        try:
            self.log_area.delete("end-2c", "end-1c")
            self.log_area.insert("end-1c", char)
            self.log_area.see("end")
        except: pass
        self.log_area.configure(state="disabled")

    def start_process(self):
        start = self.entry_start.get().strip()
        end = self.entry_end.get().strip()
        if not start or not end:
            tk.messagebox.showwarning("입력 오류, 문서를 모두 입력해주세요.")
            return

        self.btn_run.configure(state="disabled", text="탐색 중...")
        self.log_area.configure(state="normal")
        self.log_area.delete("1.0", "end")
        self.log_area.configure(state="disabled")
        
        for widget in self.canvas_frame.winfo_children(): widget.destroy()
        for widget in self.toolbar_frame.winfo_children(): widget.destroy()

        thread = threading.Thread(target=self.run_logic, args=(start, end))
        thread.daemon = True
        thread.start()

    def run_logic(self, start, end):
        pkgs = [p for p in PACKAGES if p != "customtkinter" and p != "matplotlib"]
        if not install_packages(pkgs, self.log):
            self.log(" 필수 패키지 설치 실패.")
            self.reset_button(); return

        # 1 시도
        start_time = time.time()
        path, G = find_shortest_path(start, end, self.log)
        
        success = False
        
        # 1차 시도 결과 확인
        if path:
            duration = time.time() - start_time
            self.log(f"\n [1차] 경로 발견! ({len(path)-1}단계, {duration:.2f}초)")
            self.log(f" {' -> '.join(path)}")
            
            # 그래프 및 시연
            self._visualize_and_show(G, path)
            success = show_path_selenium(path, self.log)
        
        # 2. 실패 시 정방향 탐색
        if not success:
            self.log("\n [1차 시도 실패] 링크를 찾을 수 없어 '정방향 탐색'으로 재시도합니다...")
            self.log(" [2차 시도] 정방향 탐색 (Forward-Only) 시작...")
            
            start_time = time.time()
            path, G = find_shortest_path_forward_only(start, end, self.log)
            
            if path:
                duration = time.time() - start_time
                self.log(f"\n [2차] 경로 발견! ({len(path)-1}단계, {duration:.2f}초)")
                self.log(f" {' -> '.join(path)}")
                
                self._visualize_and_show(G, path)
                show_path_selenium(path, self.log)
            else:
                self.log("\n 정방향 탐색으로도 경로를 찾지 못했습니다.ㅠ\n 입력한 단어가 위키피디아에 존재하는 글인지 다시 확인해주세요!")

        self.reset_button()

# 그래프 그리는 함수
    def _visualize_and_show(self, G, path):
        self.start_spinner(f" 그래프 배치 계산 중 (노드 {G.number_of_nodes()}개)...  ")
        import networkx as nx
        try:
            fixed_pos = {}
            path_len = len(path)
            for i, node in enumerate(path):
                x_pos = -3.0 + (6.0 * i / (path_len - 1))
                fixed_pos[node] = (x_pos, 0.0)
    
    # 데이터 로딩 너무 김        
            if G.number_of_nodes() > 500:
                self.log("\n 데이터가 많아 랜덤 배치 모드를 사용합니다.")
                pos = {}
                import random
                for node in G.nodes():
                    if node in fixed_pos: pos[node] = fixed_pos[node]
                    else: pos[node] = (random.uniform(-3.5, 3.5), random.uniform(-2.5, 2.5))
            else:
                pos = nx.spring_layout(G, pos=fixed_pos, fixed=fixed_pos.keys(), k=0.5, iterations=30)
            
            self.stop_spinner()
            self.root.after(0, lambda: self.reveal_and_draw_graph(G, path, pos))
        except Exception as e:
            self.stop_spinner()
            self.log(f" 그래프 계산 오류: {e}")

    def reveal_and_draw_graph(self, G, path, pos):
        self.show_graph_panel()
        self.draw_graph_in_gui(G, path, pos)

    def draw_graph_in_gui(self, G, path, pos):
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        import networkx as nx

        fig = Figure(figsize=(9, 5), facecolor='#2b2b2b')
        ax = fig.add_subplot(111)
        ax.set_axis_off()

        node_colors = []
        node_sizes = []
        node_alphas = []
        path_set = set(path)
        
        for node in G.nodes():
            if node in path_set:
                node_colors.append('#f1c40f')
                node_sizes.append(400)
                node_alphas.append(1.0)
            elif G.nodes[node].get('type') == 'start':
                node_colors.append('#3498db')
                node_sizes.append(300)
                node_alphas.append(1.0)
            elif G.nodes[node].get('type') == 'end':
                node_colors.append('#e74c3c')
                node_sizes.append(300)
                node_alphas.append(1.0)
            else:
                node_colors.append('#95a5a6')
                node_sizes.append(50)
                node_alphas.append(0.3)

        nx.draw_networkx_edges(G, pos, ax=ax, edge_color='#ecf0f1', alpha=0.1, width=0.5)
        nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors, node_size=node_sizes, alpha=0.3)
        
        path_edges = list(zip(path, path[1:]))
        path_nodes = list(path_set)
        nx.draw_networkx_nodes(G, pos, ax=ax, nodelist=path_nodes, node_color='#f1c40f', node_size=400)
        nx.draw_networkx_edges(G, pos, ax=ax, edgelist=path_edges, edge_color='#f1c40f', width=3.0)
        
        labels = {node: node for node in G.nodes() if node in path_set}
        nx.draw_networkx_labels(G, pos, labels, ax=ax, font_size=9, font_color='white', font_weight='bold', font_family='Malgun Gothic')

        canvas = FigureCanvasTkAgg(fig, master=self.canvas_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        toolbar = NavigationToolbar2Tk(canvas, self.toolbar_frame)
        toolbar.update()
        toolbar.pack(side="bottom", fill="x")

    def reset_button(self):
        self.stop_spinner()
        self.root.after(0, lambda: self.btn_run.configure(state="normal", text="탐색 시작"))

    def run(self):
        self.root.mainloop()


# 실행ㄱㄱ 
if __name__ == "__main__":
    try:
        import customtkinter
        import matplotlib
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter", "matplotlib"])
        import customtkinter
    
    app = ModernWikiApp()
    app.run()
