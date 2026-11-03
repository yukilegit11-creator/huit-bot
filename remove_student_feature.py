import re

def remove_student_feature(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # 1. Grid cols 5 -> 4
    html = html.replace('lg:grid-cols-5 gap-4', 'lg:grid-cols-4 gap-4')

    # 2. Remove Card 3: Sinh Viên Đã Nạp
    card3_pattern = r'<!-- Card 3: Sinh Viên Đã Nạp -->\s*<div.*?</div>\s*</div>'
    html = re.sub(card3_pattern, '', html, flags=re.DOTALL)

    # 3. Remove Header Buttons (Mở Form Nạp Sinh Viên & Sao chép Link)
    header_btn_pattern = r'<div class="flex items-center gap-2">\s*<a href="[^"]*submit-cookie".*?</div>\s*</div>\s*</div>\s*<!-- NAVIGATION TABS -->'
    replacement = '</div>\n    </div>\n\n    <!-- NAVIGATION TABS -->'
    html = re.sub(header_btn_pattern, replacement, html, flags=re.DOTALL)

    # 4. Remove Navigation Tab Button
    tab_btn_pattern = r'<button id="tabBtnStudents".*?</button>'
    html = re.sub(tab_btn_pattern, '', html, flags=re.DOTALL)

    # 5. Remove Tab Content tabStudents
    tab_content_pattern = r'<!-- TAB 2: QUẢN LÝ SINH VIÊN & AUTO-ĐĂNG KÝ -->.*?<!-- TAB 3: LIVE TERMINAL CONSOLE LOG'
    html = re.sub(tab_content_pattern, '<!-- TAB 2: LIVE TERMINAL CONSOLE LOG', html, flags=re.DOTALL)

    # 6. Remove Modals (add-student-modal, bulk-import-modal)
    add_modal_pattern = r'<!-- MODAL: THÊM SINH VIÊN MỚI -->.*?<!-- MODAL: CẬP NHẬT COOKIE ZALO -->'
    html = re.sub(add_modal_pattern, '<!-- MODAL: CẬP NHẬT COOKIE ZALO -->', html, flags=re.DOTALL)

    # 7. In JS: Update tabs array
    html = html.replace("const tabs = ['activities', 'students', 'logs', 'channels', 'history', 'config'];",
                        "const tabs = ['activities', 'logs', 'channels', 'history', 'config'];")

    # 8. In JS: Remove switchTab student branch
    html = html.replace("else if (tab === 'students') fetchStudents();\n", "")
    html = html.replace("else if (tab === 'students') fetchStudents();", "")

    # 9. In JS: Remove fetchStatus student stats updates
    html = re.sub(r'if \(data\.student_stats\) \{.*?\}', '', html, flags=re.DOTALL)
    html = re.sub(r'document\.getElementById\([\'"]tab-student-badge[\'"]\).*?;\n?', '', html)
    html = re.sub(r'document\.getElementById\([\'"]stat-total-students[\'"]\).*?;\n?', '', html)
    html = re.sub(r'document\.getElementById\([\'"]stat-student-valid-count[\'"]\).*?;\n?', '', html)

    # 10. Remove STUDENTS TAB JS functions
    students_js_pattern = r'// ================= STUDENTS TAB =================.*?// ================= STATUS & SUMMARY ================'
    html = re.sub(students_js_pattern, '// ================= STATUS & SUMMARY ================', html, flags=re.DOTALL)

    # 11. Remove student modal JS functions
    modal_funcs_pattern = r'function openAddStudentModal\(\).*?function openZaloCookieModal\(\)'
    html = re.sub(modal_funcs_pattern, 'function openZaloCookieModal()', html, flags=re.DOTALL)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Cleaned {file_path}")

remove_student_feature('c:/Users/Admin/Documents/HUIT/vaa/ufm/templates/index.html')
remove_student_feature('c:/Users/Admin/Documents/HUIT/generate_ufm_html.py')
