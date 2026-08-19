"""
围棋棋盘识别（定位 + 棋子识别 + 坐标转换）
依赖 opencv-python, numpy
不再内置窗口截图，由外部传入图片。
"""
from __future__ import annotations

import bisect
import logging
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np

log = logging.getLogger(__name__)

# ---------- 常量 ----------
BOARD_SIZE = 19
CELL_MIN = 15
CELL_MAX = 100
MIN_GRID_MATCHES = 12
MIN_BOARD_SPAN_PX = 200
MIN_BOARD_SPAN_RATIO = 0.35

# 棋子识别阈值
BLACK_THR = 80
WHITE_THR = 150
ROI_HALF_RATIO = 0.49
RING_INNER_RATIO = 0.25
RING_OUTER_RATIO = 0.48
VOTE_THRESHOLD = 0.30

# last_move 标记识别
MARKER_HALF = 0.22
MARKER_RATIO_LO = 0.02
MARKER_RATIO_HI = 0.80

# 定位相关
STONE_BLACK_THR = 80
STONE_WHITE_THR = 180


@dataclass
class BoardParams:
    """棋盘参数"""
    origin_x: int
    origin_y: int
    cell_size: float


def _boundary_darkness(gray: np.ndarray, origin: float, cell: float, axis: str) -> int:
    h, w = gray.shape[:2]
    padding = max(3, int(cell * 0.15))
    above = int(round(origin - padding))
    below = int(round(origin + 18 * cell + padding))
    total = 0
    if axis == "h":
        if 0 <= above < h:
            total += int(np.sum(gray[above, :] < 100))
        if 0 <= below < h:
            total += int(np.sum(gray[below, :] < 100))
    else:
        if 0 <= above < w:
            total += int(np.sum(gray[:, above] < 100))
        if 0 <= below < w:
            total += int(np.sum(gray[:, below] < 100))
    return total


def _find_best_origin_for_cell(sorted_vals: list[float], cell: float, image_dim: int,
                               gray: Optional[np.ndarray] = None, axis: str = "h") -> Tuple[int, Optional[float]]:
    n = len(sorted_vals)
    tolerance = cell * 0.2
    candidates: list[tuple[int, int, float]] = []
    for v in sorted_vals:
        for k0 in range(19):
            origin = v - k0 * cell
            if origin < -tolerance:
                continue
            if origin + 18 * cell > image_dim + tolerance:
                continue
            matches = 0
            for k in range(19):
                expected = origin + k * cell
                pos = bisect.bisect_left(sorted_vals, expected)
                if pos < n and abs(sorted_vals[pos] - expected) < tolerance:
                    matches += 1
                elif pos > 0 and abs(sorted_vals[pos - 1] - expected) < tolerance:
                    matches += 1
            boundary_dark = _boundary_darkness(gray, origin, cell, axis) if gray is not None else 0
            candidates.append((matches, -boundary_dark, origin))
    if not candidates:
        return 0, None
    candidates.sort(reverse=True)
    return candidates[0][0], candidates[0][2]


def _find_19_grid(values: list[float], image_dim: int,
                  gray: Optional[np.ndarray] = None, axis: str = "h") -> Optional[list[float]]:
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n < 5:
        return None
    cell_candidates: list[float] = []
    for i in range(n):
        for j in range(i + 1, n):
            d = sorted_vals[j] - sorted_vals[i]
            for N in range(1, 19):
                cell = d / N
                if CELL_MIN <= cell <= CELL_MAX:
                    cell_candidates.append(cell)
    if not cell_candidates:
        return None
    cell_candidates.sort()
    clusters: list[tuple[int, float]] = []
    i = 0
    while i < len(cell_candidates):
        j = i
        while j < len(cell_candidates) and cell_candidates[j] - cell_candidates[i] <= 1.0:
            j += 1
        if j - i >= 10:
            mid = (i + j - 1) // 2
            clusters.append((j - i, cell_candidates[mid]))
        i = j
    if not clusters:
        return None
    clusters.sort(key=lambda x: -x[0])
    overall_best_matches = 0
    overall_best_cell: Optional[float] = None
    overall_best_origin: Optional[float] = None
    for _count, cell in clusters[:10]:
        matches, origin = _find_best_origin_for_cell(sorted_vals, cell, image_dim, gray=gray, axis=axis)
        if matches > overall_best_matches:
            overall_best_matches = matches
            overall_best_cell = cell
            overall_best_origin = origin
    if overall_best_matches < MIN_GRID_MATCHES or overall_best_cell is None or overall_best_origin is None:
        return None
    return [overall_best_origin + k * overall_best_cell for k in range(19)]


def _detect_axis_aligned_lines(gray: np.ndarray, axis: str) -> list[float]:
    h, w = gray.shape[:2]
    dark = (gray < 100).astype(np.uint8)
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 1))
    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 15))
    h_ext = cv2.morphologyEx(dark, cv2.MORPH_OPEN, kernel_h)
    v_ext = cv2.morphologyEx(dark, cv2.MORPH_OPEN, kernel_v)
    if axis == "h":
        line_only = (h_ext > 0) & (v_ext == 0)
        proj = line_only.sum(axis=1).astype(np.float32)
    else:
        line_only = (v_ext > 0) & (h_ext == 0)
        proj = line_only.sum(axis=0).astype(np.float32)
    if proj.max() <= 0:
        return []
    peak_thr = max(30.0, proj.max() * 0.30)
    n = len(proj)
    above = proj > peak_thr
    positions: list[float] = []
    i = 0
    while i < n:
        if above[i]:
            run_start = i
            while i < n and above[i]:
                i += 1
            run_end = i - 1
            seg = proj[run_start:run_end + 1]
            offsets = np.arange(run_start, run_end + 1)
            center = float(np.sum(offsets * seg) / np.sum(seg))
            positions.append(center)
        else:
            i += 1
    return positions


def _locate_by_grid_structure(img: np.ndarray) -> Optional[BoardParams]:
    h, w = img.shape[:2]
    if img.shape[2] == 4:
        img = img[:, :, :3]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h_ys = _detect_axis_aligned_lines(gray, "h")
    v_xs = _detect_axis_aligned_lines(gray, "v")
    if len(h_ys) < 5 or len(v_xs) < 5:
        return None
    h_grid = _find_19_grid(h_ys, h, gray=gray, axis="h")
    v_grid = _find_19_grid(v_xs, w, gray=gray, axis="v")
    if h_grid is None or v_grid is None:
        return None
    cell_y = (h_grid[18] - h_grid[0]) / 18.0
    cell_x = (v_grid[18] - v_grid[0]) / 18.0
    if abs(cell_x - cell_y) / max(cell_x, cell_y) > 0.05:
        return None
    cell_size = (cell_x + cell_y) / 2.0
    return BoardParams(origin_x=int(round(v_grid[0])),
                       origin_y=int(round(h_grid[0])),
                       cell_size=cell_size)


def _find_board_roi(img: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    if img.ndim != 3 or img.shape[2] < 3:
        return None
    B = img[:, :, 0].astype(np.int16)
    R = img[:, :, 2].astype(np.int16)
    wood = ((R > 140) & (B < 200) & ((R - B) > 30)).astype(np.uint8) * 255
    if wood.sum() < 10000:
        return None
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25))
    closed = cv2.morphologyEx(wood, cv2.MORPH_CLOSE, kernel)
    n_lab, _lab, stats, _ = cv2.connectedComponentsWithStats(closed, 8)
    if n_lab <= 1:
        return None
    i_max = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x = int(stats[i_max, cv2.CC_STAT_LEFT])
    y = int(stats[i_max, cv2.CC_STAT_TOP])
    bw = int(stats[i_max, cv2.CC_STAT_WIDTH])
    bh = int(stats[i_max, cv2.CC_STAT_HEIGHT])
    aspect = bw / max(bh, 1)
    if aspect < 0.7 or aspect > 1.4:
        return None
    if bw < 200 or bh < 200:
        return None
    return x, y, x + bw, y + bh


def _locate_by_stone_positions(img: np.ndarray) -> Optional[BoardParams]:
    roi_box = _find_board_roi(img)
    if roi_box is None:
        return None
    x0, y0, x1, y1 = roi_box
    pad = 60
    rx0 = max(0, x0 - pad)
    ry0 = max(0, y0 - pad)
    rx1 = min(img.shape[1], x1 + pad)
    ry1 = min(img.shape[0], y1 + pad)
    sub = img[ry0:ry1, rx0:rx1]
    if sub.shape[2] == 4:
        sub = sub[:, :, :3]
    h_sub, w_sub = sub.shape[:2]
    B, G, R = sub[:, :, 0], sub[:, :, 1], sub[:, :, 2]
    is_b = ((R < STONE_BLACK_THR) & (G < STONE_BLACK_THR) & (B < STONE_BLACK_THR))
    is_w = ((R > STONE_WHITE_THR) & (G > STONE_WHITE_THR) & (B > STONE_WHITE_THR))
    mask = (is_b | is_w).astype(np.uint8)
    if mask.sum() < 500:
        return None
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    mask_eroded = cv2.erode(mask, kernel)
    n_lab, _lab, stats, centroids = cv2.connectedComponentsWithStats(mask_eroded, 8)
    xs: list[float] = []
    ys: list[float] = []
    for i in range(1, n_lab):
        a = int(stats[i, cv2.CC_STAT_AREA])
        bw = int(stats[i, cv2.CC_STAT_WIDTH])
        bh = int(stats[i, cv2.CC_STAT_HEIGHT])
        if a < 5 or a > 3000:
            continue
        if bw < 3 or bh < 3:
            continue
        ratio = bw / max(bh, 1)
        if ratio < 0.5 or ratio > 2.0:
            continue
        xs.append(float(centroids[i, 0]))
        ys.append(float(centroids[i, 1]))
    if len(xs) < BOARD_SIZE or len(ys) < BOARD_SIZE:
        return None
    h_grid = _find_19_grid(ys, h_sub, gray=None, axis="h")
    v_grid = _find_19_grid(xs, w_sub, gray=None, axis="v")
    if h_grid is None or v_grid is None:
        return None
    cell_y = (h_grid[18] - h_grid[0]) / 18.0
    cell_x = (v_grid[18] - v_grid[0]) / 18.0
    if abs(cell_x - cell_y) / max(cell_x, cell_y) > 0.05:
        return None
    cell = (cell_x + cell_y) / 2.0
    origin_x = v_grid[0] + rx0
    origin_y = h_grid[0] + ry0
    return BoardParams(origin_x=int(round(origin_x)),
                       origin_y=int(round(origin_y)),
                       cell_size=cell)


def _validate(params: BoardParams, img: np.ndarray) -> Optional[BoardParams]:
    img_h, img_w = img.shape[:2]
    span = params.cell_size * 18
    min_span = max(MIN_BOARD_SPAN_PX, max(img_w, img_h) * MIN_BOARD_SPAN_RATIO)
    if span < min_span:
        return None
    right_edge = params.origin_x + span
    bottom_edge = params.origin_y + span
    cell = params.cell_size
    if (params.origin_x < -cell or params.origin_y < -cell or
            right_edge > img_w + cell or bottom_edge > img_h + cell):
        return None
    return params


def _sanity_check_board(img: np.ndarray, params: BoardParams) -> bool:
    board, _ = _recognize_board_raw(img, params)
    for r in (0, 18):
        b = int((board[r] == 1).sum())
        w = int((board[r] == 2).sum())
        if b >= 19 or w >= 19:
            return False
    for c in (0, 18):
        b = int((board[:, c] == 1).sum())
        w = int((board[:, c] == 2).sum())
        if b >= 19 or w >= 19:
            return False
    return True


def _locate_board(img: np.ndarray) -> Optional[BoardParams]:
    params = _locate_by_grid_structure(img)
    if params is None:
        params = _locate_by_stone_positions(img)
    if params is not None:
        params = _validate(params, img)
    if params is not None and not _sanity_check_board(img, params):
        params = None
    return params


# ---------- 棋子识别函数 ----------
def _recognize_board_raw(img: np.ndarray, params: BoardParams) -> Tuple[np.ndarray, Optional[Tuple[int, int]]]:
    if img.ndim != 3 or img.shape[2] < 3:
        return np.zeros((19, 19), dtype=np.int8), None
    cs = params.cell_size
    ox = params.origin_x
    oy = params.origin_y
    h, w = img.shape[:2]
    span = 18 * cs
    x0 = max(0, int(round(ox - 0.5 * cs)))
    y0 = max(0, int(round(oy - 0.5 * cs)))
    x1 = min(w, int(round(ox + span + 0.5 * cs)))
    y1 = min(h, int(round(oy + span + 0.5 * cs)))
    if x1 - x0 < 19 or y1 - y0 < 19:
        return np.zeros((19, 19), dtype=np.int8), None
    board_area = img[y0:y1, x0:x1]
    B = board_area[:, :, 0]
    G = board_area[:, :, 1]
    R = board_area[:, :, 2]
    is_black_pix = (R < BLACK_THR) & (G < BLACK_THR) & (B < BLACK_THR)
    is_white_pix = (R >= WHITE_THR) & (G >= WHITE_THR) & (B >= WHITE_THR)
    board = np.zeros((19, 19), dtype=np.int8)
    half = max(1, int(round(ROI_HALF_RATIO * cs)))
    ring_inner = max(1, int(round(RING_INNER_RATIO * cs)))
    ring_outer = max(ring_inner + 1, int(round(RING_OUTER_RATIO * cs)))
    yy, xx = np.indices((2 * half, 2 * half))
    r_sq = (yy - half) ** 2 + (xx - half) ** 2
    ring_mask_full = ((r_sq >= ring_inner * ring_inner) &
                      (r_sq <= ring_outer * ring_outer))
    cy_arr = (oy - y0) + np.arange(19) * cs
    cx_arr = (ox - x0) + np.arange(19) * cs
    area_h, area_w = board_area.shape[:2]
    for r in range(19):
        cy = int(round(cy_arr[r]))
        y_lo = max(0, cy - half)
        y_hi = min(area_h, cy + half)
        if y_hi - y_lo < 2:
            continue
        for c in range(19):
            cx = int(round(cx_arr[c]))
            x_lo = max(0, cx - half)
            x_hi = min(area_w, cx + half)
            if x_hi - x_lo < 2:
                continue
            roi_b = is_black_pix[y_lo:y_hi, x_lo:x_hi]
            roi_w = is_white_pix[y_lo:y_hi, x_lo:x_hi]
            my_lo = y_lo - (cy - half)
            mx_lo = x_lo - (cx - half)
            ring = ring_mask_full[my_lo:my_lo + (y_hi - y_lo),
                                  mx_lo:mx_lo + (x_hi - x_lo)]
            ring_n = int(ring.sum())
            if ring_n < 8:
                continue
            ring_b_pct = float((roi_b & ring).sum()) / ring_n
            ring_w_pct = float((roi_w & ring).sum()) / ring_n
            if ring_b_pct > VOTE_THRESHOLD and ring_b_pct > ring_w_pct:
                board[r, c] = 1
            elif ring_w_pct > VOTE_THRESHOLD and ring_w_pct > ring_b_pct:
                board[r, c] = 2
    last_move = _detect_last_move_marker(img, params, board)
    return board, last_move


def _detect_last_move_marker(img: np.ndarray, params: BoardParams,
                             board: np.ndarray) -> Optional[Tuple[int, int]]:
    cs = params.cell_size
    ox = params.origin_x
    oy = params.origin_y
    h, w = img.shape[:2]
    half = max(2, int(round(MARKER_HALF * cs)))
    candidates: list[tuple[int, int, float]] = []
    for pos in np.argwhere(board != 0):
        r, c = int(pos[0]), int(pos[1])
        cy = int(round(oy + r * cs))
        cx = int(round(ox + c * cs))
        y_lo = max(0, cy - half)
        y_hi = min(h, cy + half)
        x_lo = max(0, cx - half)
        x_hi = min(w, cx + half)
        if y_hi - y_lo < 4 or x_hi - x_lo < 4:
            continue
        roi = img[y_lo:y_hi, x_lo:x_hi]
        if board[r, c] == 1:
            anti = ((roi[:, :, 0] > WHITE_THR) &
                    (roi[:, :, 1] > WHITE_THR) &
                    (roi[:, :, 2] > WHITE_THR))
        else:
            anti = ((roi[:, :, 0] < BLACK_THR) &
                    (roi[:, :, 1] < BLACK_THR) &
                    (roi[:, :, 2] < BLACK_THR))
        ratio = float(anti.mean())
        if MARKER_RATIO_LO < ratio < MARKER_RATIO_HI:
            candidates.append((r, c, ratio))
    if not candidates:
        return None
    candidates.sort(key=lambda x: -x[2])
    return (candidates[0][0], candidates[0][1])



class GoBoardCV:
    """
    野狐棋盘识别器（无内置截图，由外部传入图片）
    """

    def __init__(self, initial_image: Optional[np.ndarray] = None):
        """
        :param initial_image: 初始棋盘图片（可选），若提供则自动调用 update_board 进行定位
        """
        self._params: Optional[BoardParams] = None
        self._last_img: Optional[np.ndarray] = None

        if initial_image is not None:
            self.update_board(initial_image)

    @property
    def params(self) -> Optional[BoardParams]:
        return self._params

    def update_board(self, image: np.ndarray) -> bool:
        """
        更新棋盘图片并重新定位。
        :param image: 棋盘图片（BGR numpy 数组）
        :return: 定位成功返回 True，失败返回 False
        """
        self._last_img = image
        params = self.locate(image)
        if params is not None:
            self._params = params
            return True
        return False

    def capture(self) -> Optional[np.ndarray]:
        """
        返回最近一次更新的图片。
        注意：不再自动截图，需先调用 update_board 或通过构造函数传入图片。
        """
        return self._last_img

    def locate(self, img: Optional[np.ndarray] = None) -> Optional[BoardParams]:
        """
        定位棋盘。可传入外部截图，否则使用内部缓存的截图。
        成功则保存 params 并返回，失败返回 None。
        """
        if img is None:
            img = self._last_img
        if img is None:
            log.warning("没有可用图片，请先调用 update_board() 或传入 img")
            return None
        params = _locate_board(img)
        if params is not None:
            self._params = params
        return params

    def recognize(self, img: Optional[np.ndarray] = None,
                  params: Optional[BoardParams] = None) -> Tuple[np.ndarray, Optional[Tuple[int, int]]]:
        """
        识别盘面。
        :param img: 图片，若不提供则使用内部缓存
        :param params: 棋盘参数，若不提供则使用内部缓存的 params
        :return: (board, last_move)
        """
        if img is None:
            img = self._last_img
        if img is None:
            raise ValueError("没有可用图片")
        if params is None:
            params = self._params
        if params is None:
            raise ValueError("棋盘未定位，请先调用 locate()")
        board, last_move = _recognize_board_raw(img, params)
        return board, last_move

    def get_stone_window_coord(self, row: int, col: int) -> Tuple[int, int]:
        """
        根据棋盘坐标 (row, col) 返回图像坐标系中的像素坐标 (x, y)。
        图像左上角为 (0,0)。
        :param row: 行号 (0~18)
        :param col: 列号 (0~18)
        :return: (x, y) 图像像素坐标
        """
        if self._params is None:
            raise RuntimeError("棋盘未定位，无法计算坐标")
        ox = self._params.origin_x
        oy = self._params.origin_y
        cs = self._params.cell_size
        x = int(round(ox + col * cs))
        y = int(round(oy + row * cs))
        return x, y

    def full_cycle(self) -> Tuple[Optional[BoardParams], Optional[np.ndarray], Optional[Tuple[int, int]]]:
        """
        完整流程：使用内部缓存的图片 → 定位 → 识别。
        注意：必须先通过 update_board 或构造函数传入图片。
        :return: (params, board, last_move)
        """
        img = self.capture()
        if img is None:
            return None, None, None
        params = self.locate(img)
        if params is None:
            return None, None, None
        board, last_move = self.recognize(img, params)
        return params, board, last_move