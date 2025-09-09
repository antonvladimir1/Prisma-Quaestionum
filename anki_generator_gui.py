import sys
import genanki
import re
import os
import random
import math  # Added for the calculation
import hashlib
import pykakasi
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QLabel, QFileDialog, QTextEdit, QSizePolicy, QTabWidget,
    QTabBar, QComboBox, QStackedWidget, QFrame
)
from PyQt6.QtGui import (
    QFontDatabase, QIcon, QFont, QColor, QDesktopServices
)
from PyQt6.QtCore import Qt, QTimer, QSettings, QStandardPaths, pyqtSignal, QUrl

# --- GLOBAL CONFIGURATION ---
DEBUG = False  # Set to True for development, False for final release
PROMPTS_DIR = "Prompts"  # Subfolder for LLM prompts
# ADD THESE FOR QSETTINGS
ORGANIZATION_NAME = "PrismaQuaestionum"
APPLICATION_NAME = "PQ_Generator"

# --- SCRIPT CONFIGURATION ---
SETTINGS_FILE = "PQ_Settings.md"
ANKI_TOP_LEVEL_DECK = "[Prisma Quaestiōnum]"
MODEL_ID = 1719000001
QUAESTIONUM_FIELDS = ["Question", "Answer", "ClozeAnswer", "SVGImage", "SharedUtils"]
QUAESTIONUM_MODEL_FIELDS = [{'name': f} for f in QUAESTIONUM_FIELDS]
ICON_FILE = "icon.ico"


# --- ARTISTIC CONFIGURATION ---

IMAGE_SIZE = 1000
BACKGROUND_COLOR = "#E0DACE"  # A cleaner, warmer bone-white vellum
COLOR_PALETTE = ['#E73F5E', '#165C8E', '#6B8C4F', '#F8C3CD', '#E4A32E']
STROKE_WIDTH = 6  # The visual element we must account for
JITTER_AMOUNT = IMAGE_SIZE * 0.05 # --- NEW: Max offset for positional jitter (5% of image size) ---
MIN_SEPARATION_GAP = 25  # --- NEW: Min distance between separate shapes ---
MIN_OVERLAP_DEPTH = 30   # --- NEW: Min overlap for it to look intentional ---

# --- THE TRUE, SYMMETRICAL, AND COMPLETE HARMONIC ARMATURE (RESTRUCTURED) ---
W, H = IMAGE_SIZE, IMAGE_SIZE
HARMONIC_REGIONS = {
    'center': [(W / 2, H / 2)],
    'top_left': [(W / 3, H / 3), (W * 0.1, H * 0.1)],
    'top_right': [(2 * W / 3, H / 3), (W * 0.9, H * 0.1)],
    'bottom_left': [(W / 3, 2 * H / 3), (W * 0.1, H * 0.9)],
    'bottom_right': [(2 * W / 3, 2 * H / 3), (W * 0.9, H * 0.9)],
    'midpoints': [(W / 2, H * 0.1), (W * 0.9, H / 2), (W / 2, H * 0.9), (W * 0.1, H / 2)]
}

# Consistent Sizing Engine
BASE_SHAPE_SIZE = IMAGE_SIZE * 0.3
SIZE_VARIATION = IMAGE_SIZE * 0.15


# --- UTILITY AND DEBUG FUNCTIONS ---

def get_precise_gap(shape1, shape2):
    """
    Calculates the true, geometric gap between the fills of any two shapes.
    A negative value indicates the depth of penetration (overlap).
    """
    if shape1['type'] == 'rectangle' and shape2['type'] == 'rectangle':
        overlap_x = (shape1['width'] / 2 + shape2['width'] / 2) - abs(shape1['cx'] - shape2['cx'])
        overlap_y = (shape1['height'] / 2 + shape2['height'] / 2) - abs(shape1['cy'] - shape2['cy'])
        if overlap_x <= 0 or overlap_y <= 0:
            dx = max(0, abs(shape1['cx'] - shape2['cx']) - (shape1['width'] / 2 + shape2['width'] / 2))
            dy = max(0, abs(shape1['cy'] - shape2['cy']) - (shape1['height'] / 2 + shape2['height'] / 2))
            return math.hypot(dx, dy)
        else:
            return -min(overlap_x, overlap_y)
    elif shape1['type'] == 'circle' and shape2['type'] == 'circle':
        dist_centers = math.hypot(shape1['cx'] - shape2['cx'], shape1['cy'] - shape2['cy'])
        return dist_centers - (shape1['width'] / 2 + shape2['width'] / 2)
    else:
        circle, rect = (shape1, shape2) if shape1['type'] == 'circle' else (shape2, shape1)
        r_half_w, r_half_h = rect['width'] / 2, rect['height'] / 2
        closest_x = max(rect['cx'] - r_half_w, min(circle['cx'], rect['cx'] + r_half_w))
        closest_y = max(rect['cy'] - r_half_h, min(circle['cy'], rect['cy'] + r_half_h))
        dist = math.hypot(circle['cx'] - closest_x, circle['cy'] - closest_y)
        return dist - (circle['width'] / 2)


def get_shape_area(shape):
    """Calculates the area of a shape."""
    if shape['type'] == 'circle':
        return math.pi * (shape['width'] / 2) ** 2
    elif shape['type'] == 'rectangle':
        return shape['width'] * shape['height']
    return 0

def get_bounding_radius(shape):
    """Calculates the radius of a circle that would enclose the entire shape."""
    if shape['type'] == 'circle':
        return shape['width'] / 2
    elif shape['type'] == 'rectangle':
        # The furthest point on a rectangle is its corner.
        # We use the Pythagorean theorem to find the distance from the center to a corner.
        return math.hypot(shape['width'] / 2, shape['height'] / 2)
    return 0


def enforce_shape_boundary(shape, buffer=20):
    """
    Clamps a shape's position to be within the image boundaries,
    accounting for its bounding radius to handle rotation correctly.
    """
    # Calculate the shape's "reach" from its center to its furthest point.
    radius = get_bounding_radius(shape)

    # Clamp the center position based on this radius.
    shape['cx'] = max(shape['cx'], radius + buffer)
    shape['cx'] = min(shape['cx'], IMAGE_SIZE - radius - buffer)
    shape['cy'] = max(shape['cy'], radius + buffer)
    shape['cy'] = min(shape['cy'], IMAGE_SIZE - radius - buffer)

def transform_deeply_overlapping_rects_to_circles(composition_plan, rng):
    """Transforms heavily obscured rectangles into circles of the same area."""
    # print(f"\n{'=' * 10} CIRCLE TRANSFORMATION PHASE {'=' * 10}")
    OVERLAP_THRESHOLD = 0.75
    transformed_indices = set()
    for i, smaller_shape in enumerate(composition_plan):
        if i in transformed_indices or smaller_shape['type'] != 'rectangle': continue
        for j, larger_shape in enumerate(composition_plan):
            if i == j or j in transformed_indices or larger_shape['type'] != 'rectangle': continue
            area_smaller = smaller_shape['width'] * smaller_shape['height']
            if area_smaller >= get_shape_area(larger_shape): continue

            s_x1, s_x2 = smaller_shape['cx'] - smaller_shape['width'] / 2, smaller_shape['cx'] + smaller_shape['width'] / 2
            s_y1, s_y2 = smaller_shape['cy'] - smaller_shape['height'] / 2, smaller_shape['cy'] + smaller_shape['height'] / 2
            l_x1, l_x2 = larger_shape['cx'] - larger_shape['width'] / 2, larger_shape['cx'] + larger_shape['width'] / 2
            l_y1, l_y2 = larger_shape['cy'] - larger_shape['height'] / 2, larger_shape['cy'] + larger_shape['height'] / 2

            overlap_w = max(0, min(s_x2, l_x2) - max(s_x1, l_x1))
            overlap_h = max(0, min(s_y2, l_y2) - max(s_y1, l_y1))

            if overlap_w > 0 and overlap_h > 0:
                overlap_ratio = (overlap_w * overlap_h) / area_smaller
                # print(f"Checking Rect {i} vs Rect {j}: Overlap ratio = {overlap_ratio:.2f}")
                if overlap_ratio > OVERLAP_THRESHOLD:
                    new_radius = math.sqrt(area_smaller / math.pi)
                    buffer = STROKE_WIDTH / 2 + 10
                    cx, cy = smaller_shape['cx'], smaller_shape['cy']

                    if (cx - new_radius > buffer and cx + new_radius < IMAGE_SIZE - buffer and
                            cy - new_radius > buffer and cy + new_radius < IMAGE_SIZE - buffer):
                        # print(f"    TRANSFORMING RECTANGLE {i} TO CIRCLE.")
                        smaller_shape['type'] = 'circle'
                        smaller_shape['width'] = smaller_shape['height'] = new_radius * 2
                        available_colors = [c for c in COLOR_PALETTE if c != larger_shape['color']]
                        if not available_colors: available_colors = COLOR_PALETTE
                        smaller_shape['color'] = rng.choice(available_colors)
                        transformed_indices.add(i)
                        break
                    # else: print(f"Overlap detected, but resulting circle would be out of bounds. Skipping.")


def surgically_correct_composition(composition_plan):
    VISUAL_CONFLICT_THRESHOLD, DEEP_OVERLAP_THRESHOLD = 15, 30
    # print(f"\n{'=' * 10} SURGICAL CORRECTION PHASE {'=' * 10}")
    for i, shape_to_check in enumerate(composition_plan):
        if i == 0 or shape_to_check['type'] != 'rectangle' or shape_to_check['height'] <= shape_to_check['width']: continue
        # print(f"\n--- Checking vertical rectangle (Shape {i}) ---")
        for j, other_shape in enumerate(composition_plan):
            if i == j: continue
            fill_gap = get_precise_gap(shape_to_check, other_shape)
            visual_gap = fill_gap - STROKE_WIDTH
            # print(f"  - vs Shape {j}: Fill Gap = {fill_gap:.2f}, Visual Gap = {visual_gap:.2f}")
            is_too_close = visual_gap < VISUAL_CONFLICT_THRESHOLD
            is_deep_overlap = fill_gap < -DEEP_OVERLAP_THRESHOLD
            if is_too_close and not is_deep_overlap:
                # print(f"CONFLICT DETECTED! Visual gap ({visual_gap:.2f}) is below threshold ({VISUAL_CONFLICT_THRESHOLD}).")
                # print(f"FLIPPING RECTANGLE {i}.")
                shape_to_check['width'], shape_to_check['height'] = shape_to_check['height'], shape_to_check['width']
                break
            # else: print(f"Relationship is OK.") print(f"{'=' * 37}\n")


# --- ADD THESE THREE NEW FUNCTIONS TO THE SVG UTILITY SECTION ---

def is_shape_out_of_bounds(shape, buffer=20):
    """
    Checks if any part of a shape extends beyond the canvas buffer,
    accounting for its bounding radius to handle rotation correctly.
    """
    radius = get_bounding_radius(shape)

    if (shape['cx'] - radius < buffer or
            shape['cx'] + radius > IMAGE_SIZE - buffer or
            shape['cy'] - radius < buffer or
            shape['cy'] + radius > IMAGE_SIZE - buffer):
        return True
    return False


def find_emptiest_location(shape_to_place, other_shapes):
    """
    Finds the best candidate location on the canvas that is furthest from any other shape.
    This helps to place a relocated shape in an uncluttered area.
    """
    # --- FIX: Use the new HARMONIC_REGIONS structure ---
    candidate_points = []
    for region in HARMONIC_REGIONS.values():
        candidate_points.extend(region)

    best_location = None
    max_min_distance = -1

    for (cx, cy) in candidate_points:
        point_shape = {'type': 'circle', 'cx': cx, 'cy': cy, 'width': 0, 'height': 0}

        if not other_shapes:
            min_dist_to_neighbor = float('inf')
        else:
            min_dist_to_neighbor = min(get_precise_gap(point_shape, other) for other in other_shapes)

        if min_dist_to_neighbor > max_min_distance:
            max_min_distance = min_dist_to_neighbor
            best_location = (cx, cy)

    return best_location or (IMAGE_SIZE / 2, IMAGE_SIZE / 2)


def perform_final_composition_polish(composition_plan):
    """
    Final check to find any shapes pushed out of bounds, shrink them slightly,
    and move them to the emptiest available harmonic zone.
    """
    for i, shape in enumerate(composition_plan):
        if is_shape_out_of_bounds(shape):
            # If a shape is outside, shrink it proportionally to help it fit
            shape['width'] *= 0.9
            shape['height'] *= 0.9

            # Find all other shapes to avoid when relocating
            other_shapes = [s for j, s in enumerate(composition_plan) if i != j]

            # Find a new home for it in an uncluttered area
            new_cx, new_cy = find_emptiest_location(shape, other_shapes)
            shape['cx'], shape['cy'] = new_cx, new_cy

            # After moving, one final clamp to guarantee it's within bounds
            enforce_shape_boundary(shape)


def enforce_compositional_harmony(composition_plan):
    """
    The master reviewer. Finds visually discordant shape relationships and resolves them by
    moving the smaller shape to a harmonious 'satellite' position around the larger one.
    This is a decisive, global adjustment, not a gentle nudge.
    """
    if len(composition_plan) < 2:
        return

    for _ in range(3):
        pairs_to_check = [(composition_plan[i], composition_plan[j]) for i in range(len(composition_plan)) for j in
                          range(i + 1, len(composition_plan))]

        for shape1, shape2 in pairs_to_check:
            area1, area2 = get_shape_area(shape1), get_shape_area(shape2)
            if area1 < area2:
                offender, anchor = shape1, shape2
            else:
                offender, anchor = shape2, shape1

            gap = get_rotated_gap(offender, anchor)

            # --- SIMPLIFIED DISCORD DEFINITION ---
            # The new 'get_rotated_gap' is accurate enough to handle all cases with one rule.
            # We are in discord if the gap is between "clearly overlapping" and "clearly separate".
            is_in_awkward_zone = (gap > -MIN_OVERLAP_DEPTH and gap < MIN_SEPARATION_GAP)

            if not is_in_awkward_zone:
                continue  # This relationship is harmonious, do nothing

            # --- RESOLVE DISCORD (Logic is unchanged, but now acts on good data) ---
            offset = get_bounding_radius(anchor) + get_bounding_radius(offender) + MIN_SEPARATION_GAP
            sqrt2_offset = offset / math.sqrt(2)

            satellite_points = [
                (anchor['cx'] + offset, anchor['cy']),
                (anchor['cx'] + sqrt2_offset, anchor['cy'] - sqrt2_offset),
                (anchor['cx'], anchor['cy'] - offset),
                (anchor['cx'] - sqrt2_offset, anchor['cy'] - sqrt2_offset),
                (anchor['cx'] - offset, anchor['cy']),
                (anchor['cx'] - sqrt2_offset, anchor['cy'] + sqrt2_offset),
                (anchor['cx'], anchor['cy'] + offset),
                (anchor['cx'] + sqrt2_offset, anchor['cy'] + sqrt2_offset),
            ]

            other_shapes = [s for s in composition_plan if s is not offender and s is not anchor]
            best_point = None
            max_min_distance = -1

            for cx, cy in satellite_points:
                temp_shape_for_bounds_check = {'type': offender['type'], 'cx': cx, 'cy': cy, 'width': offender['width'],
                                               'height': offender['height']}
                if is_shape_out_of_bounds(temp_shape_for_bounds_check, buffer=30):
                    continue

                point_shape = {'type': 'circle', 'cx': cx, 'cy': cy, 'width': 0, 'height': 0}
                if not other_shapes:
                    min_dist_to_neighbor = float('inf')
                else:
                    min_dist_to_neighbor = min(get_precise_gap(point_shape, other) for other in other_shapes)

                if min_dist_to_neighbor > max_min_distance:
                    max_min_distance = min_dist_to_neighbor
                    best_point = (cx, cy)

            if best_point:
                offender['cx'], offender['cy'] = best_point
                if offender['type'] == 'rectangle':
                    offender['rotation'] = 0


def is_point_in_shape(px, py, shape):
    """Accurately checks if a point (px, py) is inside a given shape, accounting for rotation."""
    cx, cy = shape['cx'], shape['cy']

    if shape['type'] == 'circle':
        return math.hypot(px - cx, py - cy) <= shape['width'] / 2

    elif shape['type'] == 'rectangle':
        w, h = shape['width'], shape['height']
        angle = math.radians(shape.get('rotation', 0))

        # Translate the point so the shape's center is the origin
        translated_x = px - cx
        translated_y = py - cy

        # Rotate the point backwards by the shape's rotation angle
        cos_a = math.cos(-angle)
        sin_a = math.sin(-angle)
        rotated_x = translated_x * cos_a - translated_y * sin_a
        rotated_y = translated_x * sin_a + translated_y * cos_a

        # Check if the un-rotated point is within the simple axis-aligned rectangle
        return (abs(rotated_x) <= w / 2) and (abs(rotated_y) <= h / 2)

    return False


def get_rotated_gap(shape1, shape2):
    """
    The definitive, rotation-aware gap calculation. It accurately detects both
    separation and overlap by using a robust point-in-shape test.
    """
    # --- Phase 0: Quick exit for simple cases ---
    if shape1['type'] == 'circle' and shape2['type'] == 'circle':
        return get_precise_gap(shape1, shape2)

    # --- Phase 1: Perimeter Sampling ---
    # We only need to generate perimeter points once.
    def get_perimeter_points(shape):
        points = []
        cx, cy, w, h = shape['cx'], shape['cy'], shape['width'], shape['height']
        if shape['type'] == 'circle':
            # For circles, we sample points on the circumference
            num_samples = 24  # A good number for circles
            for i in range(num_samples):
                angle = 2 * math.pi * i / num_samples
                points.append((cx + (w / 2) * math.cos(angle), cy + (w / 2) * math.sin(angle)))
            return points

        # For rectangles, sample the four corners (most important) and edges
        half_w, half_h = w / 2, h / 2
        corners = [(-half_w, -half_h), (half_w, -half_h), (half_w, half_h), (-half_w, half_h)]
        edge_points = []
        for i in range(4):
            p1 = corners[i]
            p2 = corners[(i + 1) % 4]
            # Add a few points between the corners
            for t in [0.25, 0.5, 0.75]:
                edge_points.append((p1[0] * (1 - t) + p2[0] * t, p1[1] * (1 - t) + p2[1] * t))

        local_points = corners + edge_points

        angle = math.radians(shape.get('rotation', 0))
        if angle == 0:
            return [(px + cx, py + cy) for px, py in local_points]

        cos_a, sin_a = math.cos(angle), math.sin(angle)
        return [(px * cos_a - py * sin_a + cx, px * sin_a + py * cos_a + cy) for px, py in local_points]

    points1 = get_perimeter_points(shape1)
    points2 = get_perimeter_points(shape2)

    # --- Phase 2: Overlap Detection ---
    # Check if any point of one shape is inside the other
    is_overlapping = False
    for p in points1:
        if is_point_in_shape(p[0], p[1], shape2):
            is_overlapping = True
            break
    if not is_overlapping:
        for p in points2:
            if is_point_in_shape(p[0], p[1], shape1):
                is_overlapping = True
                break

    # --- Phase 3: Distance Calculation ---
    min_dist_sq = float('inf')
    for p1 in points1:
        for p2 in points2:
            dist_sq = (p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq

    distance = math.sqrt(min_dist_sq)

    # If we detected an overlap, return the distance as a negative number
    # This now correctly represents a shallow overlap.
    if is_overlapping:
        return -distance
    else:
        return distance

def svg_header():
    return f'<svg width="{IMAGE_SIZE}" height="{IMAGE_SIZE}" viewBox="0 0 {IMAGE_SIZE} {IMAGE_SIZE}" xmlns="http://www.w3.org/2000/svg">'


def draw_shape(shape_data):
    """Draws a shape, applying rotation if present."""
    draw_type, color = shape_data['type'], shape_data['color']
    fill_color, stroke_color = color, '#1a1a1a'

    if draw_type == 'circle':
        cx, cy, radius = shape_data['cx'], shape_data['cy'], shape_data['width'] / 2
        return f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="{fill_color}" stroke="{stroke_color}" stroke-width="{STROKE_WIDTH}" />'

    elif draw_type == 'rectangle':
        x = shape_data['cx'] - shape_data['width'] / 2
        y = shape_data['cy'] - shape_data['height'] / 2

        # --- NEW: Check for and apply rotation ---
        rotation = shape_data.get('rotation', 0)
        transform_attr = ""
        if rotation != 0:
            # The transform attribute rotates the shape around its own center point
            transform_attr = f' transform="rotate({rotation} {shape_data["cx"]} {shape_data["cy"]})"'

        return (f'<rect x="{x}" y="{y}" width="{shape_data["width"]}" height="{shape_data["height"]}"'
                f' fill="{fill_color}" stroke="{stroke_color}" stroke-width="{STROKE_WIDTH}"{transform_attr} />')


def create_svg_for_term(term, output_path):
    """Generates a compositional SVG for a given term and saves it to a specific path."""
    kks = pykakasi.Kakasi()
    result = kks.convert(term)
    romaji_string = "".join([item['hepburn'] for item in result])
    seed_string = romaji_string if term != romaji_string else term
    hex_dna = hashlib.sha256(seed_string.encode('utf-8')).hexdigest()
    rng = random.Random(hex_dna)
    shape_types = ['circle', 'rectangle']
    num_shapes = 2 + (int(hex_dna[0:2], 16) % 4)
    dna_pointer = 2

    # --- ROBUST COMPOSITIONAL DIRECTOR ---
    composition_plan = []
    available_regions = {name: list(points) for name, points in HARMONIC_REGIONS.items()}
    region_density = {name: 0 for name in available_regions}
    MAX_DENSITY_PER_REGION = 2

    # 1. Place the FOCAL shape
    focal_region_options = ['top_left', 'top_right', 'bottom_left', 'bottom_right']
    focal_region_name = focal_region_options[int(hex_dna[dna_pointer], 16) % len(focal_region_options)]
    focal_point = rng.choice(available_regions[focal_region_name])

    available_regions[focal_region_name].remove(focal_point)
    region_density[focal_region_name] += 1

    focal_shape_type = shape_types[int(hex_dna[dna_pointer + 1], 16) % len(shape_types)]
    focal_color = COLOR_PALETTE[int(hex_dna[dna_pointer + 2], 16) % len(COLOR_PALETTE)]
    focal_size = BASE_SHAPE_SIZE + SIZE_VARIATION

    focal_shape = {
        'type': focal_shape_type, 'color': focal_color, 'cx': focal_point[0], 'cy': focal_point[1],
        'rotation': 0, 'width': focal_size, 'height': focal_size
    }
    if focal_shape_type == 'rectangle':
        aspect_ratio = 1.0 + (int(hex_dna[dna_pointer + 3], 16) / 15.0)
        focal_shape['height'] *= aspect_ratio

    composition_plan.append(focal_shape)
    dna_pointer += 8

    # 2. Place the REMAINING shapes with stable logic
    region_names = list(available_regions.keys())

    for i in range(1, num_shapes):
        rng.shuffle(region_names)  # Shuffle order for variety each time
        shape_was_placed = False

        # Find a suitable region to place the next shape
        for region_name in region_names:
            if region_density[region_name] < MAX_DENSITY_PER_REGION and available_regions[region_name]:
                # This region is a valid candidate. Place the shape here.
                point = rng.choice(available_regions[region_name])
                available_regions[region_name].remove(point)
                region_density[region_name] += 1
                cx, cy = point

                # Create the shape
                shape_type = shape_types[int(hex_dna[dna_pointer], 16) % len(shape_types)]
                color = COLOR_PALETTE[int(hex_dna[dna_pointer + 1], 16) % len(COLOR_PALETTE)]
                size_offset = (int(hex_dna[dna_pointer + 2], 16) / 15 * SIZE_VARIATION) - (SIZE_VARIATION / 2)
                size = BASE_SHAPE_SIZE * 0.5 + size_offset

                jitter_factor_x = (int(hex_dna[dna_pointer + 3], 16) / 7.5) - 1
                jitter_factor_y = (int(hex_dna[dna_pointer + 4], 16) / 7.5) - 1

                rotation = 0
                if shape_type == 'rectangle':
                    possible_rotations = [0, 0, 0, 15, 30, 45, 90, -15, -30, -45, -90]
                    rotation = possible_rotations[int(hex_dna[dna_pointer + 5], 16) % len(possible_rotations)]

                shape_dict = {
                    'type': shape_type, 'color': color, 'cx': cx + (jitter_factor_x * JITTER_AMOUNT),
                    'cy': cy + (jitter_factor_y * JITTER_AMOUNT), 'rotation': rotation, 'width': size, 'height': size
                }

                if shape_type == 'rectangle':
                    aspect_ratio = 1.0 + (int(hex_dna[dna_pointer + 6], 16) / 15.0)
                    shape_dict['height'] *= aspect_ratio

                composition_plan.append(shape_dict)
                dna_pointer += 8
                shape_was_placed = True
                break  # Exit the inner loop (over regions) and move to the next shape

        if not shape_was_placed:
            break  # No valid regions left, stop trying to place shapes

        # --- FINAL HIERARCHY OF COMPOSITIONAL CORRECTIONS ---
        # 1. Initial clamp to bring all generated shapes onto the canvas.
        for shape in composition_plan: enforce_shape_boundary(shape)

        # 2. Transform any rectangles that are too deeply obscured into circles.
        transform_deeply_overlapping_rects_to_circles(composition_plan, rng)

        # 3. Run the master harmony enforcement to resolve all awkward relationships.
        enforce_compositional_harmony(composition_plan)

        # 4. Correct the orientation of any tall rectangles that create visual tension.
        surgically_correct_composition(composition_plan)

        # 5. A final boundary check and polish to clean up any minor issues from the harmony step.
        perform_final_composition_polish(composition_plan)

    # --- SVG STRING ASSEMBLY (Unchanged) ---
    svg_list = [svg_header(), f'<rect width="100%" height="100%" fill="{BACKGROUND_COLOR}" />']
    for shape_data in composition_plan: svg_list.append(draw_shape(shape_data))
    svg_list.extend([
        f'<text x="{IMAGE_SIZE - 220}" y="{IMAGE_SIZE - 40}" font-family="Arial, sans-serif" font-size="0" fill="#555">{term}</text>',
        '</svg>'])
    svg_string = '\n'.join(svg_list)

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(svg_string)
    except Exception as e:
        print(f"ERROR writing SVG file '{output_path}': {e}")

    # --- REMOVED: No longer generating PNG ---


# --- PARSING & HELPER FUNCTIONS ---
def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def parse_settings_file(filepath):
    """Parses the .md settings file to extract templates."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return None, f"ERROR: Settings file '{filepath}' not found."

    pattern = re.compile(r"## (.*?)\s+```[a-z]+\s+(.*?)```", re.DOTALL | re.IGNORECASE)
    matches = pattern.findall(content)
    settings = {header.lower().replace(' template', ''): code for header, code in matches}

    required_keys = ['front', 'back', 'styling']
    if not all(key in settings for key in required_keys):
        missing = [key for key in required_keys if key not in settings]
        return None, f"ERROR: Settings file is missing required sections: {', '.join(missing)}"
    return settings, None


def sanitize_for_filename(text):
    """Sanitizes a string to be a valid filename."""
    # First, replace common separators with a single underscore
    text = re.sub(r'[ /()&]', '_', text)
    # Then, remove any characters that are not alphanumeric, underscore, or hyphen
    sanitized = re.sub(r'[^\w\s-]', '', text).strip()
    # Replace remaining whitespace sequences with a single underscore
    sanitized = re.sub(r'\s+', '_', sanitized)
    return sanitized[:50]


# --- ADD THIS NEW HELPER FUNCTION ---
def save_backup_file(deck_name, couplets_text):
    """Saves the couplets text to a backup .md file."""
    # This uses the same logic from the old CoupletCatcher
    docs_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    save_path = os.path.join(docs_path, "Prismata")
    os.makedirs(save_path, exist_ok=True)

    filename = f"{sanitize_for_filename(deck_name)}.md"
    full_path = os.path.join(save_path, filename)

    try:
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(couplets_text)
        return full_path  # Return the path of the saved file
    except Exception as e:
        print(f"Error saving backup file: {e}")
        return None


# --- CORE ANKI DECK CREATION LOGIC ---
def create_anki_deck(input_data, deck_name_str, anki_settings, font_files):
    """Creates an Anki deck from either a file path or a string of text."""
    lines = []
    if os.path.exists(str(input_data)):
        try:
            with open(input_data, 'r', encoding='utf-8') as f:
                lines = f.read().strip().split('\n')
        except Exception as e:
            return False, f"ERROR: Could not read input file. Reason: {e}", [], None
    else:
        lines = input_data.strip().split('\n')

    if not lines or all(not line.strip() for line in lines):
        return False, "ERROR: Input data is empty or contains only whitespace.", [], None

    anki_model = genanki.Model(
        MODEL_ID, 'Prisma Quaestionum v2.3',
        fields=QUAESTIONUM_MODEL_FIELDS,
        templates=[{'name': 'Card 1', 'qfmt': anki_settings['front'], 'afmt': anki_settings['back']}],
        css=anki_settings['styling']
    )

    full_deck_name = f"{ANKI_TOP_LEVEL_DECK}::{deck_name_str}"
    anki_deck = genanki.Deck(random.randrange(1 << 30, 1 << 31), full_deck_name)

    docs_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    output_dir = os.path.join(docs_path, "Prismata")
    os.makedirs(output_dir, exist_ok=True)

    media_output_dir = os.path.join(output_dir, "media")
    os.makedirs(media_output_dir, exist_ok=True)

    generated_media_files = []
    notes_created = 0
    warnings = []

    for i, row in enumerate(lines):
        if not row.strip() or "Question;Answer" in row: continue
        if row.count(';') > 1:
            warnings.append(f"Line {i + 1}: Skipped (multiple semicolons). Content: '{row[:80]}...'")
            continue
        if row.count(';') != 1: continue

        question, original_answer_line = [p.strip() for p in row.split(';')]
        cloze_match = re.search(r'\*(.*?)\*', original_answer_line)
        if not cloze_match: continue

        notes_created += 1
        inner_text = cloze_match.group(1).strip()

        svg_filename = f"pq_img_{sanitize_for_filename(inner_text)}.svg"
        full_svg_path = os.path.join(media_output_dir, svg_filename)

        create_svg_for_term(inner_text, full_svg_path)

        generated_media_files.append(full_svg_path)

        # --- FIX: Create the full HTML tag for the field ---
        svg_field_content = f'<img src="{svg_filename}" alt="Compositional SVG for {inner_text}">'

        anki_note = genanki.Note(
            model=anki_model,
            # --- FIX: Use the new HTML string instead of just the filename ---
            fields=[question, original_answer_line, inner_text, svg_field_content, ""],
            tags=['Prisma_Quaestionum']
        )
        anki_deck.add_note(anki_note)

    if not anki_deck.notes:
        return False, "No valid notes were processed. No file will be created.", warnings, None

    anki_package = genanki.Package(anki_deck)
    anki_package.media_files = [get_resource_path(f) for f in font_files]
    anki_package.media_files.extend(generated_media_files)

    output_filename = f"{sanitize_for_filename(deck_name_str)}.apkg"
    full_output_path = os.path.join(output_dir, output_filename)
    anki_package.write_to_file(full_output_path)

    return True, f"Successfully created '{output_filename}' with {notes_created} cards.", warnings, full_output_path


class ClickableLabel(QLabel):
    """A QLabel that emits a 'clicked' signal when clicked."""
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

# --- NEW PROMPT ASSISTANT LOGIC ---
class PromptAssistantWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.prompts = self.load_prompts()
        self.status_reset_timer = QTimer(self)
        self.status_reset_timer.setSingleShot(True)
        self.status_reset_timer.timeout.connect(self.reset_status)
        self.init_ui()

    # --- SURGICAL REFACTOR: Helper for centered buttons ---
    @staticmethod
    def _create_centered_button_layout(button):
        """Creates a centered QHBoxLayout for a given button."""
        layout = QHBoxLayout()
        layout.addStretch()
        layout.addWidget(button)
        layout.addStretch()
        return layout

    # ... load_prompts and calculate_n are unchanged ...
    def load_prompts(self):
        """Loads all .md prompts from the Prompts subdirectory."""
        prompts = {}
        prompt_dir_path = get_resource_path(PROMPTS_DIR)
        if not os.path.isdir(prompt_dir_path):
            return {"Error": "Prompt directory not found."}

        for filename in os.listdir(prompt_dir_path):
            if filename.startswith("Prism of Questions - ") and filename.endswith(".md"):
                try:
                    lang_name = filename.replace("Prism of Questions - ", "").replace(".md", "")
                    with open(os.path.join(prompt_dir_path, filename), 'r', encoding='utf-8') as f:
                        prompts[lang_name] = f.read()
                except Exception as e:
                    print(f"Error loading prompt {filename}: {e}")
        return prompts

    def calculate_n(self, text_content):
        """Calculates the N value based on word count."""
        word_count = len(text_content.split())
        modifier = 1.25
        divisor = 150
        division_result = word_count / divisor
        floored_result = math.floor(division_result)
        multiplication_result = floored_result * modifier
        final_n = round(multiplication_result)
        return final_n

    # In class PromptAssistantWidget
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        # We reduce the main spacing to let the stretch factors define the space
        layout.setSpacing(10)

        # --- TOP CONTROLS (STRETCH = 1) ---
        lang_layout = QHBoxLayout()
        lang_label = QLabel("Prompt Language:")
        self.lang_combo = QComboBox()
        if self.prompts:
            sorted_langs = sorted(self.prompts.keys())
            self.lang_combo.addItems(sorted_langs)
            default_text = "English (Modern)"
            if default_text in sorted_langs:
                self.lang_combo.setCurrentText(default_text)
        lang_layout.addWidget(lang_label)
        lang_layout.addWidget(self.lang_combo)

        # --- WORKSPACE (STRETCH = 8) ---
        materia_label = QLabel("Paste Māteria Prima Below:")
        self.materia_input = QTextEdit()
        self.materia_input.setPlaceholderText("Paste the text to process here...")
        self.materia_input.textChanged.connect(self.update_clear_button_visibility)

        # --- ACTION AREA (STRETCH = 5) ---
        # 1. Create the buttons
        self.process_button = QPushButton("Generate && Copy Prompt")
        self.process_button.setObjectName("processPromptButton")
        self.process_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.process_button.clicked.connect(self.process_and_copy)

        self.clear_button = QPushButton("Clear")
        self.clear_button.setObjectName("clearButton")
        self.clear_button.clicked.connect(self.clear_fields)
        self.clear_button.hide()

        # 2. Arrange buttons in the stable horizontal layout
        left_container = QWidget()
        left_layout = QHBoxLayout(left_container); left_layout.setContentsMargins(0,0,0,0)
        left_layout.addStretch(); left_layout.addWidget(self.clear_button)
        center_container = QWidget()
        center_layout = QHBoxLayout(center_container); center_layout.setContentsMargins(0,0,0,0)
        center_layout.addWidget(self.process_button)
        right_container = QWidget()
        button_layout = QHBoxLayout()
        button_layout.addWidget(left_container, 1)
        button_layout.addWidget(center_container, 0)
        button_layout.addWidget(right_container, 1)

        # 3. Create the status label
        self.status_label = QLabel("Ready.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setMinimumHeight(25) # Give it some breathing room

        # 4. Group the button layout and status label vertically
        action_area_layout = QVBoxLayout()
        action_area_layout.setSpacing(10)
        action_area_layout.addLayout(button_layout)
        action_area_layout.addWidget(self.status_label)


        # --- FINAL LAYOUT ASSEMBLY WITH MASCULINE FIBONACCI RATIOS (1:8:5) ---
        layout.addLayout(lang_layout, stretch=1)
        layout.addWidget(materia_label, stretch=0) # Labels don't stretch
        layout.addWidget(self.materia_input, stretch=8)
        layout.addLayout(action_area_layout, stretch=5)

    def clear_fields(self):
        """Public method to clear input fields."""
        self.materia_input.clear()
        self.status_label.setText("Ready.")

    def update_clear_button_visibility(self):
        """Shows or hides the clear button based on input."""
        has_text = bool(self.materia_input.toPlainText().strip())
        self.clear_button.setVisible(has_text)

    def reset_status(self):
        self.status_label.setText("Ready.")

    def process_and_copy(self):
        # I've added the timer start calls back to the error checks for robustness
        materia_text = self.materia_input.toPlainText().strip()
        selected_lang = self.lang_combo.currentText()

        if not materia_text:
            self.status_label.setText("Error: Māteria Prima cannot be empty.")
            self.status_reset_timer.start(3000)
            return
        if not selected_lang or selected_lang == "Error":
            self.status_label.setText("Error: No prompts loaded.")
            self.status_reset_timer.start(3000)
            return

        n_value = self.calculate_n(materia_text)
        base_prompt = self.prompts[selected_lang]
        final_prompt = re.sub(r"(\(N\)\s*:\s*\[.*?\])", f"(N): [{n_value}]", base_prompt, flags=re.IGNORECASE)
        full_clipboard_text = f"{final_prompt}\n\n{materia_text}"
        clipboard = QApplication.clipboard()
        clipboard.setText(full_clipboard_text)

        self.status_label.setText(f"Success! N={n_value}. Prompt copied to clipboard.")
        self.status_reset_timer.start(2000)

# --- ADD THIS HELPER FUNCTION ---
def open_file_externally(filepath):
    """Opens a file using the system's default application."""
    if not os.path.exists(filepath):
        print(f"Error: Cannot open file, path not found: {filepath}")
        return
    url = QUrl.fromLocalFile(filepath)
    QDesktopServices.openUrl(url)


# --- FINAL, CORRECTED COUPLET CATCHER WIDGET ---
class CoupletCatcherWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = QSettings(ORGANIZATION_NAME, APPLICATION_NAME)
        # --- TIMER INITIALIZATION (This was missing) ---
        self.status_reset_timer = QTimer(self)
        self.status_reset_timer.setSingleShot(True)
        self.status_reset_timer.timeout.connect(self.reset_status_label)
        # -----------------------------------------------
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)  # Vertical spacing between components

        # --- Top layout with Paste button and Deck Name ---
        top_layout = QHBoxLayout()
        self.paste_button = QPushButton("Paste Couplets")
        self.paste_button.setObjectName("selectFileButton")
        self.paste_button.setToolTip("Paste text from your clipboard into the editor below")
        self.paste_button.clicked.connect(self.populate_from_clipboard)

        self.deck_name_input = QLineEdit()
        self.deck_name_input.setPlaceholderText("Enter Deck Name")
        self.deck_name_input.textChanged.connect(self.update_state)

        top_layout.addWidget(self.paste_button)
        top_layout.addWidget(self.deck_name_input)

        # --- Main text area ---
        self.couplets_input = ClickableTextEdit()
        self.couplets_input.setObjectName("coupletsInput")  # Give it a name for styling
        self.couplets_input.setPlaceholderText(
            "Paste couplets (Ctrl+V), click the button above,\nor double-click here to load a file."
        )
        self.couplets_input.textChanged.connect(self.update_state)
        self.couplets_input.doubleClicked.connect(self.populate_from_file)

        # --- Bottom layout with Save button and Status label ---
        self.save_button = QPushButton("Save Couplets as .md")
        self.save_button.setObjectName("saveCoupletsButton")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_couplets)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self.save_button)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.status_label)

        # --- HORIZONTAL SEPARATOR LINES ---
        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.HLine)
        line1.setObjectName("separatorLine")

        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setObjectName("separatorLine")


        # --- SENSUAL FIBONACCI LAYOUT (3:5:2 RATIO) ---
        main_layout.addLayout(top_layout, stretch=3)
        main_layout.addWidget(line1, stretch=0) # Lines have no stretch
        main_layout.addWidget(self.couplets_input, stretch=5)
        main_layout.addWidget(line2, stretch=0) # Lines have no stretch
        main_layout.addLayout(bottom_layout, stretch=2)
        # --- END OF LAYOUT ---

        self.update_state()

    def populate_from_clipboard(self):
        clipboard = QApplication.clipboard()
        self.couplets_input.setPlainText(clipboard.text())
        self.deck_name_input.setFocus()

    def populate_from_file(self):
        docs_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        default_open_path = os.path.join(docs_path, "Prismata")
        file_filter = "Markdown Files (*.md);;Text Files (*.txt)"
        filepath, _ = QFileDialog.getOpenFileName(self, "Select Couplet File", default_open_path, file_filter)
        if filepath:
            self.handle_file_data(filepath)
            self.deck_name_input.setFocus()

    def handle_file_data(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.couplets_input.setPlainText(f.read())
        except Exception as e:
            self.couplets_input.setPlainText(f"Error loading file:\n{e}")
        base_name = os.path.splitext(os.path.basename(filepath))[0]
        self.deck_name_input.setText(base_name.replace('_', ' ').replace('-', ' - '))

    def update_state(self):
        """Single method to update the state of the save button and status label."""
        has_name = bool(self.deck_name_input.text().strip())
        has_text = bool(self.couplets_input.toPlainText().strip())
        is_ready = has_name and has_text

        self.save_button.setEnabled(is_ready)

        # Only show "Ready to save." if the timer isn't active
        if not self.status_reset_timer.isActive():
            if is_ready:
                self.status_label.setText("Ready to save.")
            else:
                self.status_label.setText("")

    def save_couplets(self):
        deck_name = self.deck_name_input.text().strip()
        couplets_text = self.couplets_input.toPlainText().strip()

        saved_path = save_backup_file(deck_name, couplets_text)

        if saved_path:
            filename = os.path.basename(saved_path)
            self.status_label.setText(f"Success! Saved as '{filename}'")
            self.status_reset_timer.start(3000)
        else:
            self.status_label.setText("Error saving file.")
            self.status_reset_timer.start(5000)

    def clear_fields(self):
        self.deck_name_input.clear()
        self.couplets_input.clear()
        self.update_state()  # This will now correctly clear the status label

    def reset_status_label(self):
        """Resets the status label based on the current input state."""
        self.update_state()

# --- CUSTOM CLICKABLE QLINEEDIT WIDGET ---
class ClickableLineEdit(QLineEdit):
    """A QLineEdit that emits a 'clicked' signal when clicked."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setReadOnly(True) # Make it look static, but it will be clickable

    def mousePressEvent(self, event):
        # We override this event to do our custom action
        self.parent().change_save_location()
        # We don't call the base class event, so the cursor doesn't appear


# --- SIMPLIFIED DECK GENERATOR WIDGET ---
class DeckGeneratorWidget(QWidget):
    def __init__(self, font_files, parent_app):
        super().__init__()
        self.input_filepath = ""
        self.font_files = font_files
        self.parent_app = parent_app
        self.settings = QSettings(ORGANIZATION_NAME, APPLICATION_NAME)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # --- BLOCK 1: CONFIGURATION AREA (STRETCH = 3) ---
        # We'll group all setup controls into a single layout.
        config_layout = QVBoxLayout()
        config_layout.setSpacing(10) # Tighter spacing within the block

        # Top controls for file selection
        file_layout = QHBoxLayout()
        self.file_label = QLabel("No file selected.")
        self.file_label.setObjectName("fileLabel")
        self.select_file_button = QPushButton("Select Couplets File")
        self.select_file_button.setObjectName("selectFileButton")
        self.select_file_button.clicked.connect(self.select_file)
        file_layout.addWidget(self.file_label)
        file_layout.addStretch()
        file_layout.addWidget(self.select_file_button)

        # Deck name input
        self.deck_name_input = QLineEdit()
        self.deck_name_input.setPlaceholderText("Enter Deck Name (auto-filled from file)")

        # Add the components to the config block
        config_layout.addLayout(file_layout)
        config_layout.addWidget(self.deck_name_input)


        # --- BLOCK 2: COMMAND AREA (STRETCH = 2) ---
        # The existing stable button layout works perfectly for this.
        self.generate_button = QPushButton("Generate Anki Deck")
        self.generate_button.setObjectName("generateButton")
        self.generate_button.clicked.connect(self.run_generation)

        self.clear_all_button = QPushButton("Clear All")
        self.clear_all_button.setObjectName("utilityButton")
        self.clear_all_button.clicked.connect(self.parent_app.clear_all_fields)

        self.install_deck_button = QPushButton("Install Deck")
        self.install_deck_button.setObjectName("utilityButton")
        self.install_deck_button.clicked.connect(self.install_last_deck)
        self.install_deck_button.hide()

        left_container = QWidget()
        center_container = QWidget()
        center_layout = QHBoxLayout(center_container); center_layout.setContentsMargins(0,0,0,0)
        center_layout.addWidget(self.generate_button)
        right_container = QWidget()
        right_layout = QHBoxLayout(right_container); right_layout.setContentsMargins(0,0,0,0)
        right_layout.addWidget(self.clear_all_button); right_layout.addWidget(self.install_deck_button)
        right_layout.addStretch()

        button_layout = QHBoxLayout()
        button_layout.addWidget(left_container, 1)
        button_layout.addWidget(center_container, 0)
        button_layout.addWidget(right_container, 1)


        # --- BLOCK 3: LOG/OUTPUT AREA (STRETCH = 8) ---
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setObjectName("statusBox")
        self.log_box.setPlaceholderText("Logs and status messages will appear here...")


        # --- FINAL ASSEMBLY WITH MASCULINE FIBONACCI RATIOS (3:2:8) ---
        main_layout.addLayout(config_layout, stretch=3)
        main_layout.addLayout(button_layout, stretch=2)
        main_layout.addWidget(self.log_box, stretch=8)

    def select_file(self):
        docs_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        default_open_path = os.path.join(docs_path, "Prismata")
        file_filter = "Markdown Files (*.md);;Text Files (*.txt)"
        filepath, _ = QFileDialog.getOpenFileName(self, "Select Couplet File", default_open_path, file_filter)
        if filepath:
            self.handle_dropped_file(filepath)

    def run_generation(self):
        self.log_box.clear()
        deck_name = self.deck_name_input.text().strip()
        if not self.input_filepath:
            self.log_box.setText("ERROR: Please select a source file.")
            return
        if not deck_name:
            self.log_box.setText("ERROR: Please provide a deck name.")
            return

        self.log_box.append(f"Loading settings from {SETTINGS_FILE}...")
        QApplication.processEvents()

        anki_settings, error = parse_settings_file(get_resource_path(SETTINGS_FILE))
        if error:
            self.log_box.append(error)
            return

        self.log_box.append("Settings loaded successfully.\n")
        self.log_box.append(f"Processing '{os.path.basename(self.input_filepath)}'...")
        QApplication.processEvents()

        success, message, warnings, output_path = create_anki_deck(
            self.input_filepath, deck_name, anki_settings, self.font_files
        )

        if success:
            self.log_box.append(f"\n--- GENERATION COMPLETE ---")
            self.log_box.append(message)
            self.parent_app.deck_generation_complete(output_path)
        else:
            self.log_box.append(f"\n--- GENERATION FAILED ---")
            self.log_box.append(message)
            self.install_deck_button.hide()

        if warnings:
            self.log_box.append("\n--- WARNINGS ---")
            for warning in warnings: self.log_box.append(warning)

    def handle_dropped_file(self, filepath):
        self.input_filepath = filepath
        self.file_label.setText(os.path.basename(filepath))
        base_name = os.path.splitext(os.path.basename(filepath))[0]
        self.deck_name_input.setText(base_name.replace('_', ' ').replace('-', ' - '))
        self.log_box.setText(f"File '{os.path.basename(filepath)}' loaded. Ready to generate.")

    def clear_fields(self):
        self.input_filepath = ""
        self.file_label.setText("No file selected.")
        self.deck_name_input.clear()
        self.log_box.clear()
        self.install_deck_button.hide()

    def install_last_deck(self):
        if self.parent_app.last_deck_path:
            open_file_externally(self.parent_app.last_deck_path)

# --- ADD THIS NEW CUSTOM WIDGET CLASS ---
class ClickableTextEdit(QTextEdit):
    """A QTextEdit that emits a signal on double-click."""
    doubleClicked = pyqtSignal()

    def mouseDoubleClickEvent(self, event):
        # We emit our custom signal first
        self.doubleClicked.emit()
        # Then call the base class implementation
        super().mouseDoubleClickEvent(event)


# --- MAIN APPLICATION WINDOW (Now with Tabs) ---
class AnkiGeneratorApp(QWidget):
    def __init__(self):
        super().__init__()
        # --- ADDITIONS FOR THEME MANAGEMENT ---
        self.settings = QSettings(ORGANIZATION_NAME, APPLICATION_NAME)
        # Load theme, defaulting to 'dark' if it's the first run
        self.current_theme = self.settings.value("theme", "light")
        self.last_deck_path = None  # To store the path of the last generated deck
        # ------------------------------------
        self.font_files = [

        ]
        self.load_fonts()
        self.init_ui()
        self.apply_styles() # This will now apply the loaded theme

    def load_fonts(self):
        if DEBUG: print("--- Loading Application Fonts ---")
        for font_file in self.font_files:
            font_path = get_resource_path(font_file)
            if os.path.exists(font_path):
                font_id = QFontDatabase.addApplicationFont(font_path)
                if DEBUG and font_id != -1:
                    family = QFontDatabase.applicationFontFamilies(font_id)[0]
                    print(f"Loaded '{font_file}' -> Family Name: '{family}'")
        if DEBUG: print("---------------------------------")

    # In class AnkiGeneratorApp
    def init_ui(self):
        self.setWindowTitle('Prisma Quaestiōnum')
        self.setWindowIcon(QIcon(get_resource_path(ICON_FILE)))
        self.setGeometry(300, 300, 750, 650)
        self.setMinimumSize(650, 550)
        self.setObjectName("mainAppWindow")

        # --- ADD/MODIFY THESE LINES ---
        # 1. Add the "Always on Top" flag
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        # 2. Enable drag-and-drop for the whole window
        self.setAcceptDrops(True)
        # 3. Restore the window's last position and size
        self.restore_window_state()
        # ----------------------------

        # This is the main layout for the whole window
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(20)  # Spacing for main elements (title from tabs)

        # --- CHANGE: Use ClickableLabel and connect it ---
        self.title_label = ClickableLabel("Prisma Quaestiōnum")
        self.title_label.setObjectName("titleLabel")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Provide visual feedback that it's clickable
        self.title_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.title_label.clicked.connect(self.toggle_theme)  # Connect to our new method
        main_layout.addWidget(self.title_label)
        # -------------------------------------------------

        # --- THE THREE-TAB LAYOUT ---
        tab_widget_layout = QVBoxLayout()
        tab_widget_layout.setSpacing(0)
        self.tab_bar = QTabBar()
        self.tab_bar.setExpanding(True)
        self.content_pages = QStackedWidget()
        self.content_pages.setObjectName("contentPane")
        tab_widget_layout.addWidget(self.tab_bar)
        tab_widget_layout.addWidget(self.content_pages)
        main_layout.addLayout(tab_widget_layout)

        # --- Create and add the THREE pages ---
        self.prompt_assistant_tab = PromptAssistantWidget()
        self.couplet_catcher_tab = CoupletCatcherWidget()
        self.deck_generator_tab = DeckGeneratorWidget(self.font_files, self)

        self.tab_bar.addTab("Prompt Assistant")
        self.content_pages.addWidget(self.prompt_assistant_tab)

        self.tab_bar.addTab("Couplet Catcher")
        self.content_pages.addWidget(self.couplet_catcher_tab)

        self.tab_bar.addTab("Deck Generator")
        self.content_pages.addWidget(self.deck_generator_tab)

        self.tab_bar.currentChanged.connect(self.content_pages.setCurrentIndex)

    def restore_window_state(self):
        """Restores window size and position from settings."""
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            # Fallback for first launch
            self.setGeometry(300, 300, 750, 650)  # Made slightly larger for new buttons

    def save_window_state(self):
        """Saves window size and position to settings."""
        self.settings.setValue("geometry", self.saveGeometry())

    def closeEvent(self, event):
        """Overrides the close event to save window state."""
        self.save_window_state()
        super().closeEvent(event)

    def dragEnterEvent(self, event):
        """Checks if the dragged data is a file."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Handles the dropped file."""
        urls = event.mimeData().urls()
        if urls:
            filepath = urls[0].toLocalFile()
            # Check if it's a valid file type
            if filepath.lower().endswith(('.txt', '.md')):
                # Switch to the Deck Generator tab (now index 2)
                self.tab_bar.setCurrentIndex(2)
                self.deck_generator_tab.handle_dropped_file(filepath)
            else:
                # Show error in the new log_box
                self.tab_bar.setCurrentIndex(1)
                self.deck_generator_tab.log_box.setText("ERROR: Please drop a .txt or .md file.")
                self.deck_generator_tab.central_area.setCurrentIndex(1)  # Switch to log view

    def clear_all_fields(self):
        """Calls the clear method on each tab."""
        self.prompt_assistant_tab.clear_fields()
        self.couplet_catcher_tab.clear_fields()
        self.deck_generator_tab.clear_fields()

    def deck_generation_complete(self, filepath):
        """Callback function when a deck is successfully created."""
        self.last_deck_path = filepath
        self.deck_generator_tab.install_deck_button.show()

    def toggle_theme(self):
        """Switches the theme, saves the choice, and reapplies styles."""
        self.current_theme = "light" if self.current_theme == "dark" else "dark"
        self.settings.setValue("theme", self.current_theme)
        self.apply_styles()

    # In class AnkiGeneratorApp
    def apply_styles(self):
        # (The palette definitions are unchanged)
        light_palette = {
            "bg": "#FFFFFF", "text": "#333333", "text_strong": "#000000",
            "text_subtle": "#444444", "border": "#cccccc", "input_bg": "#f0f0f0",
            "input_bg_clickable": "#E2E8F0", "input_text_clickable": "#4A5568",
            "input_border_clickable": "#A0AEC0", "active_tab_border": "#E65100"
        }
        dark_palette = {
            "bg": "#1A202C", "text": "#E2E8F0", "text_strong": "#FFFFFF",
            "text_subtle": "#A0AEC0", "border": "#4A5568", "input_bg": "#2D3748",
            "input_bg_clickable": "#2D3748", "input_text_clickable": "#A0AEC0",
            "input_border_clickable": "#718096", "active_tab_border": "#F6AD55"
        }
        palette = dark_palette if self.current_theme == "dark" else light_palette

        stylesheet = f"""
            #mainAppWindow {{ background-color: {palette["bg"]}; }}
            #contentPane {{ border: 1px solid {palette["border"]}; }}
            QTabBar::tab {{
                background-color: {palette["input_bg"]};
                border: 1px solid {palette["border"]};
                border-bottom-color: transparent;
                padding: 10px;
                font-family: ''; font-weight: 300; font-size: 16px;
                color: {palette["text"]};
                qproperty-textRendering: "AntialiasedText";
            }}
            QTabBar::tab:selected {{
                background-color: {palette["bg"]};
                border-top: 3px solid {palette["active_tab_border"]};
                color: {palette["text_strong"]};
                border-bottom-color: {palette["bg"]};
                margin-bottom: -1px;
                qproperty-textRendering: "AntialiasedText";
            }}
            #titleLabel {{
                font-family: ''; font-weight: 900; font-style: italic;
                font-size: 32px; color: {palette["text_strong"]}; padding-bottom: 5px;
                qproperty-textRendering: "AntialiasedText";
            }}
            QLabel {{
                font-family: ''; font-weight: 300;
                font-size: 16px; color: {palette["text_subtle"]};
                qproperty-textRendering: "AntialiasedText";
            }}
            QLineEdit, QComboBox {{
                background-color: {palette["input_bg"]}; border: 1px solid {palette["border"]};
                padding: 10px; border-radius: 4px; color: {palette["text"]};
                font-family: ''; font-weight: 300; font-size: 16px;
                qproperty-textRendering: "AntialiasedText";
            }}

            /* --- CORRECTED TEXTEDIT STYLES --- */
            QTextEdit {{
                background-color: {palette["input_bg"]}; border: 1px solid {palette["border"]};
                padding: 10px; border-radius: 4px; color: {palette["text"]};
                font-family: '', monospace; font-size: 14px;
            }}
            #coupletsInput[hasText="false"] {{
                border-style: dashed;
            }}
            /* ---------------------------------- */

            #pathDisplayEdit {{
                background-color: {palette["input_bg_clickable"]};
                color: {palette["input_text_clickable"]};
                border: 1px dashed {palette["input_border_clickable"]};
            }}

            /* --- ADDED FOR POLISH --- */
            #separatorLine {{
                border: none;
                border-top: 1px solid {palette["border"]};
                margin: 5px 0px;
            }}
            /* ----------------------- */

            QPushButton {{
                color: #FFFFFF; border: none; padding: 10px 15px; border-radius: 5px;
                font-family: ''; font-weight: 500; font-size: 14px;
                qproperty-textRendering: "AntialiasedText";
            }}

    /* --- FINAL "GHOSTLY" RULE FOR DISABLED BUTTONS --- */
    /* This uses semi-transparent colors which is more reliable than opacity */
    QPushButton:disabled {{
        background-color: rgba(113, 128, 150, 150); /* Mid-gray at ~60% opacity */
        color: rgba(255, 255, 255, 100); /* White at ~40% opacity */
    }}
    /* --------------------------------------------------- */

            #selectFileButton {{ background-color: #7D5295; }} #selectFileButton:hover {{ background-color: #DA70D6; }}
            #generateButton {{ background-color: #2E8B57; }} #generateButton:hover {{ background-color: #9CCC65; }}
            #processPromptButton {{ background-color: #E65100; }} #processPromptButton:hover {{ background-color: #FFB300; }}
            #saveCoupletsButton {{ background-color: #4A5568; }} #saveCoupletsButton:hover {{ background-color: #718096; }}
            #clearButton {{ background-color: #A0AEC0; }} #clearButton:hover {{ background-color: #CBD5E0; }}
            #utilityButton {{ font-size: 12px; padding: 8px 12px; background-color: #4A5568; }}
            #utilityButton:hover {{ background-color: #718096; }}
        """
        self.setStyleSheet(stylesheet)
        self.title_label.setToolTip(f"Switch to {'Light' if self.current_theme == 'dark' else 'Dark'} Mode")


if __name__ == "__main__":
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    window = AnkiGeneratorApp()
    window.show()
    sys.exit(app.exec())
