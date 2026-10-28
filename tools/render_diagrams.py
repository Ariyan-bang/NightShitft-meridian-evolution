"""UML Diagram Renderer using Pillow.
Generates publication-quality PNG class diagrams for:
1. Facade Pattern (ExportBridge)
2. Hard-Coded / Decayed Registry Pattern (deck.py vs soilconf.py)
"""
import os
from PIL import Image, ImageDraw, ImageFont

FONT_FAMILY = "C:/Windows/Fonts/segoeui.ttf"
FONT_BOLD = "C:/Windows/Fonts/segoeuib.ttf"
FONT_ITALIC = "C:/Windows/Fonts/segoeuii.ttf"
FONT_MONO = "C:/Windows/Fonts/consola.ttf"

def get_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

def draw_rounded_rect(draw, bbox, radius, fill, outline, width=2):
    draw.rounded_rectangle(bbox, radius=radius, fill=fill, outline=outline, width=width)

def draw_arrow(draw, start, end, fill="#334155", width=2, dashed=False, arrow_type="open", label="", label_pos="center", label_bg="#F8FAFC"):
    x1, y1 = start
    x2, y2 = end
    
    if dashed:
        import math
        dist = math.hypot(x2 - x1, y2 - y1)
        if dist == 0:
            return
        dash_len = 8
        gap_len = 5
        cur = 0
        while cur < dist:
            cur_end = min(cur + dash_len, dist)
            sx = x1 + (x2 - x1) * (cur / dist)
            sy = y1 + (y2 - y1) * (cur / dist)
            ex = x1 + (x2 - x1) * (cur_end / dist)
            ey = y1 + (y2 - y1) * (cur_end / dist)
            draw.line([(sx, sy), (ex, ey)], fill=fill, width=width)
            cur += dash_len + gap_len
    else:
        draw.line([start, end], fill=fill, width=width)
        
    import math
    angle = math.atan2(y2 - y1, x2 - x1)
    head_len = 12
    if arrow_type == "open":
        left_x = x2 - head_len * math.cos(angle - math.pi / 6)
        left_y = y2 - head_len * math.sin(angle - math.pi / 6)
        right_x = x2 - head_len * math.cos(angle + math.pi / 6)
        right_y = y2 - head_len * math.sin(angle + math.pi / 6)
        draw.line([(x2, y2), (left_x, left_y)], fill=fill, width=width)
        draw.line([(x2, y2), (right_x, right_y)], fill=fill, width=width)
    elif arrow_type == "closed":
        left_x = x2 - head_len * math.cos(angle - math.pi / 6)
        left_y = y2 - head_len * math.sin(angle - math.pi / 6)
        right_x = x2 - head_len * math.cos(angle + math.pi / 6)
        right_y = y2 - head_len * math.sin(angle + math.pi / 6)
        draw.polygon([(x2, y2), (left_x, left_y), (right_x, right_y)], fill="#FFFFFF", outline=fill)
    elif arrow_type == "diamond":
        dx = head_len * math.cos(angle)
        dy = head_len * math.sin(angle)
        perp_x = (head_len / 1.5) * math.cos(angle + math.pi / 2)
        perp_y = (head_len / 1.5) * math.sin(angle + math.pi / 2)
        p1 = (x1, y1)
        p2 = (x1 + dx + perp_x, y1 + dy + perp_y)
        p3 = (x1 + 2 * dx, y1 + 2 * dy)
        p4 = (x1 + dx - perp_x, y1 + dy - perp_y)
        draw.polygon([p1, p2, p3, p4], fill="#FFFFFF", outline=fill)
    elif arrow_type == "filled_diamond":
        dx = head_len * math.cos(angle)
        dy = head_len * math.sin(angle)
        perp_x = (head_len / 1.5) * math.cos(angle + math.pi / 2)
        perp_y = (head_len / 1.5) * math.sin(angle + math.pi / 2)
        p1 = (x1, y1)
        p2 = (x1 + dx + perp_x, y1 + dy + perp_y)
        p3 = (x1 + 2 * dx, y1 + 2 * dy)
        p4 = (x1 + dx - perp_x, y1 + dy - perp_y)
        draw.polygon([p1, p2, p3, p4], fill=fill, outline=fill)

    if label:
        font = get_font(FONT_FAMILY, 12)
        t_bbox = draw.textbbox((0, 0), label, font=font)
        tw = t_bbox[2] - t_bbox[0]
        th = t_bbox[3] - t_bbox[1]
        
        if label_pos == "center":
            lx = (x1 + x2) / 2 - tw / 2
            ly = (y1 + y2) / 2 - th / 2
        elif label_pos == "above":
            lx = (x1 + x2) / 2 - tw / 2
            ly = (y1 + y2) / 2 - th - 5
        elif label_pos == "right":
            lx = (x1 + x2) / 2 + 8
            ly = (y1 + y2) / 2 - th / 2
            
        if label_bg:
            draw.rectangle([lx - 3, ly - 2, lx + tw + 3, ly + th + 2], fill=label_bg)
        draw.text((lx, ly), label, fill=fill, font=font)


def draw_uml_class(draw, x, y, w, stereotype, name, fields, methods, header_fill, body_fill="#FFFFFF", border_color="#334155"):
    font_bold = get_font(FONT_BOLD, 15)
    font_italic = get_font(FONT_ITALIC, 12)
    font_mono = get_font(FONT_MONO, 13)
    
    line_h = 20
    header_h = 48 if stereotype else 36
    fields_h = len(fields) * line_h + 12 if fields else 0
    methods_h = len(methods) * line_h + 12 if methods else 0
    total_h = header_h + fields_h + methods_h
    
    # Outer box
    draw_rounded_rect(draw, [x, y, x + w, y + total_h], 6, body_fill, border_color, 2)
    
    # Header box
    draw.rounded_rectangle([x, y, x + w, y + header_h], radius=6, fill=header_fill, outline=border_color, width=2)
    draw.rectangle([x, y + header_h - 6, x + w, y + header_h], fill=header_fill)
    draw.line([(x, y + header_h), (x + w, y + header_h)], fill=border_color, width=2)
    
    # Title text
    cur_y = y + 6
    if stereotype:
        st_text = f"«{stereotype}»"
        st_bbox = draw.textbbox((0, 0), st_text, font=font_italic)
        st_w = st_bbox[2] - st_bbox[0]
        draw.text((x + (w - st_w) / 2, cur_y), st_text, fill="#475569", font=font_italic)
        cur_y += 18
        
    name_bbox = draw.textbbox((0, 0), name, font=font_bold)
    name_w = name_bbox[2] - name_bbox[0]
    draw.text((x + (w - name_w) / 2, cur_y), name, fill="#0F172A", font=font_bold)
    
    # Fields
    cur_y = y + header_h + 8
    for f in fields:
        draw.text((x + 12, cur_y), f, fill="#1E293B", font=font_mono)
        cur_y += line_h
        
    if fields and methods:
        draw.line([(x, y + header_h + fields_h), (x + w, y + header_h + fields_h)], fill=border_color, width=1)
        cur_y = y + header_h + fields_h + 8
        
    for m in methods:
        draw.text((x + 12, cur_y), m, fill="#1E293B", font=font_mono)
        cur_y += line_h
        
    return x, y, w, total_h


def render_facade_diagram(out_path):
    width, height = 1520, 1080
    img = Image.new("RGB", (width, height), "#F8FAFC")
    draw = ImageDraw.Draw(img)
    
    title_font = get_font(FONT_BOLD, 22)
    sub_font = get_font(FONT_FAMILY, 14)
    note_font = get_font(FONT_FAMILY, 13)
    note_bold = get_font(FONT_BOLD, 13)
    
    # Title header
    draw.text((50, 24), "Genuine Design Pattern: Facade Pattern (ExportBridge)", fill="#0F172A", font=title_font)
    draw.text((50, 56), "Location: analytics/meridian/exportbridge.py:73 | Architectural Boundary: External Reporting vs Internal SQLite", fill="#64748B", font=sub_font)
    
    # Package Boundaries
    # Reporting Subsystem Package (Left)
    draw_rounded_rect(draw, [40, 100, 420, 1020], 8, "#F0F9FF", "#0284C7", 2)
    draw.text((60, 115), "Package: Reporting Subsystem (Client)", fill="#0369A1", font=get_font(FONT_BOLD, 15))
    
    # Analytics Subsystem Package (Right)
    draw_rounded_rect(draw, [460, 100, 1480, 1020], 8, "#F8FAFC", "#475569", 2)
    draw.text((480, 115), "Package: Analytics & Orchestration (Internal Subsystem)", fill="#334155", font=get_font(FONT_BOLD, 15))
    
    # Classes
    # 1. Reporting Client
    c1 = draw_uml_class(draw, 70, 190, 320, "Client", "ReportingClient", 
                        ["- report_dir: str"], 
                        ["+ generate_annual_report()", "+ list_available_runs()"],
                        header_fill="#BAE6FD", border_color="#0284C7")
    
    # 2. ExportBridge (Facade)
    c2 = draw_uml_class(draw, 500, 190, 430, "Facade", "ExportBridge",
                        ["- store: Store"],
                        ["+ __init__(store: Store)",
                         "+ manifest(): List[Dict]",
                         "+ for_station_year(stnid, yr): ExportedForecast",
                         "+ for_station(stnid): List[ExportedForecast]",
                         "+ export_all(): List[ExportedForecast]"],
                        header_fill="#BBF7D0", border_color="#16A34A")
                        
    # 3. Store (Internal DB)
    c3 = draw_uml_class(draw, 1040, 190, 390, "Internal Store", "Store",
                        ["- conn: sqlite3.Connection",
                         "- path: str"],
                        ["+ list_forecasts(): List[ForecastRow]",
                         "+ get_forecast(stnid, yr): ForecastRow",
                         "+ daily_rows(stnid, yr): List[DailyRow]",
                         "+ save_result(result, run_at)"],
                        header_fill="#FED7AA", border_color="#EA580C")
                        
    # 4. Aggregate Module (Internal Arithmetic)
    c4 = draw_uml_class(draw, 1040, 410, 390, "Internal Logic", "aggregate module",
                        [],
                        ["+ summarize_stored(store, stnid, yr)",
                         "+ summarize_result(result: ForecastResult)",
                         "- compute_stress_days(daily_rows)"],
                        header_fill="#FED7AA", border_color="#EA580C")
                        
    # 5. ExportedForecast (DTO)
    c5 = draw_uml_class(draw, 500, 460, 430, "Value Object / DTO", "ExportedForecast",
                        ["+ format_version: str = '1.0'",
                         "+ stnid: str",
                         "+ year: int",
                         "+ run_at: str",
                         "+ model: str",
                         "+ yield_t: float",
                         "+ ndays: int",
                         "+ summary: Dict",
                         "+ daily: List[ExportedDaily]"],
                        ["+ to_dict(): Dict"],
                        header_fill="#FEF08A", border_color="#CA8A04")
                        
    # 6. ExportedDaily (DTO item)
    c6 = draw_uml_class(draw, 500, 750, 430, "Value Object", "ExportedDaily",
                        ["+ doy: int", "+ sw: float", "+ et: float", 
                         "+ drain: float", "+ biom: float", "+ lai: float"],
                        ["+ from_row(r: DailyRow): ExportedDaily"],
                        header_fill="#FEF08A", border_color="#CA8A04")
                        
    # Connectors
    # ReportingClient -> ExportBridge
    draw_arrow(draw, (390, 260), (500, 260), fill="#0284C7", width=2, dashed=True, arrow_type="open", label="«invokes»", label_pos="above", label_bg="#F0F9FF")
    
    # ExportBridge -> Store
    draw_arrow(draw, (930, 260), (1040, 260), fill="#16A34A", width=2, dashed=False, arrow_type="open", label="wraps / queries", label_pos="above", label_bg="#F8FAFC")
    
    # ExportBridge -> aggregate
    draw_arrow(draw, (850, 370), (1040, 440), fill="#16A34A", width=2, dashed=True, arrow_type="open", label="calls math", label_pos="above", label_bg="#F8FAFC")
    
    # ExportBridge -> ExportedForecast
    draw_arrow(draw, (715, 385), (715, 460), fill="#16A34A", width=2, dashed=True, arrow_type="open", label="creates", label_pos="right", label_bg="#F8FAFC")
    
    # ExportedForecast *-> ExportedDaily (Composition)
    draw_arrow(draw, (715, 715), (715, 750), fill="#CA8A04", width=2, dashed=False, arrow_type="filled_diamond", label="contains", label_pos="right", label_bg="#F8FAFC")
    
    # ReportingClient ..> ExportedForecast (Consumes DTO)
    draw_arrow(draw, (390, 330), (500, 520), fill="#0284C7", width=2, dashed=True, arrow_type="open", label="consumes DTO", label_pos="center", label_bg="#F8FAFC")
    
    # Note Box
    draw_rounded_rect(draw, [1040, 580, 1440, 840], 8, "#FEFCE8", "#EAB308", 2)
    draw.text((1060, 600), "Facade Pattern Justification:", fill="#713F12", font=note_bold)
    note_lines = [
        "• CONTRACTS.md: 'reporting reads forecast tables.'",
        "• Before Facade: Reporting executed raw SQL against",
        "  forecast & forecast_daily, coupling it to schema layout.",
        "• Facade Solution: ExportBridge wraps the SQLite",
        "  handle and seasonal arithmetic (aggregate.py).",
        "• Information Hiding: Returns clean, versioned DTOs",
        "  (format_version 1.0) with zero live DB handles.",
        "• Judgement: KEEP. Vital architectural seam."
    ]
    ny = 635
    for nl in note_lines:
        draw.text((1060, ny), nl, fill="#854D0E", font=note_font)
        ny += 24

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, dpi=(150, 150))
    print(f"Saved Facade diagram to: {out_path}")


def render_hardcoded_registry_diagram(out_path):
    width, height = 1520, 1050
    img = Image.new("RGB", (width, height), "#F8FAFC")
    draw = ImageDraw.Draw(img)
    
    title_font = get_font(FONT_BOLD, 22)
    sub_font = get_font(FONT_FAMILY, 14)
    note_font = get_font(FONT_FAMILY, 13)
    note_bold = get_font(FONT_BOLD, 13)
    
    # Title header
    draw.text((50, 24), "Degenerate Pattern: Decayed / Hard-Coded Registry", fill="#0F172A", font=title_font)
    draw.text((50, 56), "Location: analytics/meridian/deck.py:34-55 vs soilconf.py:88 | Decayed 2008 stopgap bypassing 2026 registry", fill="#64748B", font=sub_font)
    
    # Left Box: ACTIVE PRODUCTION PATH (DECAYED)
    draw_rounded_rect(draw, [40, 100, 730, 990], 8, "#FEF2F2", "#DC2626", 2)
    draw.text((60, 115), "ACTIVE PRODUCTION PIPELINE (Decayed Hard-Coded Path)", fill="#B91C1C", font=get_font(FONT_BOLD, 15))
    
    # Right Box: ORPHANED MODERN REGISTRY (UNWIRED)
    draw_rounded_rect(draw, [760, 100, 1480, 990], 8, "#F5F3FF", "#7C3AED", 2)
    draw.text((780, 115), "ORPHANED 2026 ARCHITECTURE (Never Wired into Production)", fill="#6D28D9", font=get_font(FONT_BOLD, 15))
    
    # Left Classes (Production)
    c_cron = draw_uml_class(draw, 70, 160, 420, "Nightly Batch CLI", "run_forecast.py",
                            ["+ --db: str = 'meridian.db'",
                             "+ --station: Optional[str]",
                             "+ --year: Optional[int]",
                             "+ --parallel: bool",
                             "-- NO soil-config CLI flag! --"],
                            ["+ main()"],
                            header_fill="#FEE2E2", border_color="#DC2626")
                            
    c_orch = draw_uml_class(draw, 70, 360, 420, "Orchestration Module", "orchestrator.py",
                            [],
                            ["+ build_spec(store, stnid, yr): ModelInputSpec",
                             "+ run_station_year(...)",
                             "+ run_all(store, config)"],
                            header_fill="#FEE2E2", border_color="#DC2626")
                            
    c_deck = draw_uml_class(draw, 70, 520, 670, "Degenerate Registry", "deck.py (Hard-Coded Dicts)",
                            ["+ SOIL = {'GUELPH': (0.150, 1100.0), 'KITCHNER': (0.142, 1050.0),",
                             "           'WATERLOO': (0.138, 1000.0), 'CAMBRIDG': (0.155, 1200.0),",
                             "           'MILTON': (0.148, 950.0), 'BRANTFRD': (0.162, 900.0)}",
                             "+ DEFAULT_SOIL = (0.145, 1000.0)",
                             "+ LATITUDE = {'GUELPH': 43.545, 'KITCHNER': 43.451, ...}",
                             "+ DEFAULT_LAT = 43.545"],
                            ["+ soil_for(stnid: str): Tuple[float, float]",
                             "+ latitude_for(stnid: str): float",
                             "+ spec_from_readings(stnid, yr, readings): ModelInputSpec"],
                            header_fill="#FECACA", border_color="#B91C1C")
                            
    # Right Classes (Modern Orphaned)
    c_reg = draw_uml_class(draw, 790, 160, 420, "Proper Registry Pattern", "SoilRegistry (soilconf.py)",
                           ["+ stations: Mapping[str, SoilParams]",
                            "+ defaults: Optional[SoilParams]"],
                           ["+ soil_for(stnid: str): SoilParams",
                            "+ {static} from_yaml(path: str): SoilRegistry",
                            "+ {static} from_ini(path: str): SoilRegistry",
                            "+ from_mapping(dict): SoilRegistry"],
                           header_fill="#DDD6FE", border_color="#7C3AED")
                           
    c_params = draw_uml_class(draw, 790, 380, 420, "Validated Value Object", "SoilParams",
                              ["+ awc: float",
                               "+ rooting_depth_mm: float",
                               "+ latitude: Optional[float] = None"],
                              ["+ validate(stnid: str)  # Enforces QC envelopes"],
                              header_fill="#DDD6FE", border_color="#7C3AED")
                              
    c_yaml = draw_uml_class(draw, 1260, 160, 190, "External File", "soil.sample.yaml",
                            ["stations:", "  GUELPH: ...", "  KITCHNER: ...", "defaults: ..."],
                            [],
                            header_fill="#E2E8F0", border_color="#64748B")
                            
    c_unwired = draw_uml_class(draw, 790, 560, 420, "Orphaned Seam", "soilconf module",
                               [],
                               ["+ spec_from_readings_with(registry, ...)",
                                "  # Zero production callers in entire repo!"],
                               header_fill="#EDE9FE", border_color="#7C3AED")

    # Connectors - Active Path
    draw_arrow(draw, (280, 290), (280, 360), fill="#DC2626", width=2, dashed=False, arrow_type="open", label="invokes batch", label_pos="right", label_bg="#FEF2F2")
    draw_arrow(draw, (280, 445), (280, 520), fill="#DC2626", width=2, dashed=False, arrow_type="open", label="calls spec_from_readings()", label_pos="right", label_bg="#FEF2F2")
    
    # Connectors - Modern Path
    draw_arrow(draw, (1000, 332), (1000, 380), fill="#7C3AED", width=2, dashed=False, arrow_type="filled_diamond", label="aggregates", label_pos="right", label_bg="#F5F3FF")
    draw_arrow(draw, (1210, 205), (1260, 205), fill="#7C3AED", width=2, dashed=True, arrow_type="open", label="parses config", label_pos="above", label_bg="#F5F3FF")
    draw_arrow(draw, (1000, 508), (1000, 560), fill="#7C3AED", width=2, dashed=True, arrow_type="open", label="uses", label_pos="right", label_bg="#F5F3FF")
    
    # MISSING SEAM (Big Red Dashed Line with Cross)
    draw_arrow(draw, (490, 410), (790, 580), fill="#DC2626", width=3, dashed=True, arrow_type="open", label="MISSING SEAM: Never invoked in production!", label_pos="above", label_bg="#F8FAFC")
    
    # Left note: Degenerate explanation
    draw_rounded_rect(draw, [70, 770, 710, 950], 6, "#FEF2F2", "#DC2626", 2)
    draw.text((90, 785), "Why It Is Degenerate (Decayed as Code Changed):", fill="#991B1B", font=note_bold)
    note_left = [
        "• 2008 stopgap (MRD-91) placed 6 hard-coded stations into deck.py.",
        "• Adding stations or tuning soil parameters requires modifying source code,",
        "  running test suites, and creating new software deployments.",
        "• Modern registry (SoilRegistry) was built in 2026 but left strictly opt-in,",
        "  leaving the production pipeline permanently tethered to the 2008 dictionary."
    ]
    ny = 815
    for nl in note_left:
        draw.text((90, ny), nl, fill="#B91C1C", font=note_font)
        ny += 22
        
    # Right note: Recommendation
    draw_rounded_rect(draw, [790, 680, 1450, 950], 6, "#F0FDF4", "#16A34A", 2)
    draw.text((810, 700), "Judgement & Architectural Remedy:", fill="#14532D", font=note_bold)
    note_right = [
        "• Judgement: REMOVE hardcoded dictionaries; COMPLETE the migration to SoilRegistry.",
        "• Step 1: Add '--soil-config' argument to run_forecast.py CLI.",
        "• Step 2: Wire orchestrator.build_spec() to load SoilRegistry from config or fallback.",
        "• Step 3: Deprecate SOIL dict in deck.py, fulfilling MRD-91 without schema churn."
    ]
    ny = 735
    for nr in note_right:
        draw.text((810, ny), nr, fill="#166534", font=note_font)
        ny += 24
        
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, dpi=(150, 150))
    print(f"Saved Hard-Coded Registry diagram to: {out_path}")


if __name__ == "__main__":
    facade_png = os.path.abspath("docs/diagrams/facade_pattern.png")
    registry_png = os.path.abspath("docs/diagrams/hardcoded_registry_pattern.png")
    render_facade_diagram(facade_png)
    render_hardcoded_registry_diagram(registry_png)
