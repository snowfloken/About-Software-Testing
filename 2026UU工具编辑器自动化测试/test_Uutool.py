import os
import time
from datetime import datetime
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


@pytest.fixture( scope="function" )
def driver():
    # 提交最终代码脚本时，请将驱动路径换回官方路径"C:\\Program Files\\Google\\Chrome\\Application\\chromedriver.exe"
    service = Service(
        executable_path="C:\\Program Files\\Google\\Chrome\\Application\\chromedriver.exe" )
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Chrome(service=service, options=options)
    driver.get( "https://uutool.cn/tinymce/" )
    driver.maximize_window()
    driver.implicitly_wait( 10 )
    yield driver
    driver.quit()


class TestUutool:

    # test-code-start

    EDITOR_URL = "https://uutool.cn/tinymce/"
    IFRAME_ID = "mytextarea_ifr"

    # ------------------------------------------------------------------
    # 一、通用操作封装
    # ------------------------------------------------------------------
    def open_editor(self, driver):
        """打开编辑器页面，清空编辑区内容并滚动到编辑器位置，保证每条用例起始状态一致。"""
        driver.get( self.EDITOR_URL )
        WebDriverWait( driver, 30 ).until(
            EC.presence_of_element_located( (By.CSS_SELECTOR, ".tox-tinymce") ) )
        time.sleep( 2 )
        self.clear_editor( driver )
        self.scroll_to_editor( driver )

    def scroll_to_editor(self, driver):
        """将编辑器滚动到固定顶部栏下方，使菜单栏、工具栏与正文同时出现在截图区域。"""
        driver.execute_script(
            "var el = document.querySelector('.tox-tinymce');"
            "if (!el) { return; }"
            "var rect = el.getBoundingClientRect();"
            "window.scrollTo(0, window.scrollY + rect.top - 120);" )
        time.sleep( 0.5 )

    def clear_editor(self, driver):
        """点击编辑器底部【清空】按钮，清除编辑区与本地存储中的内容。"""
        button = driver.find_element( By.CSS_SELECTOR, ".js-reset" )
        driver.execute_script( "arguments[0].scrollIntoView({block: 'center'});", button )
        time.sleep( 0.3 )
        button.click()
        time.sleep( 1 )

    def enter_editor(self, driver):
        """切换到正文编辑区的 iframe，并返回可编辑的 body 元素。"""
        driver.switch_to.frame( driver.find_element( By.ID, self.IFRAME_ID ) )
        return driver.find_element( By.TAG_NAME, "body" )

    def leave_editor(self, driver):
        driver.switch_to.default_content()

    def type_lines(self, driver, lines):
        """在编辑区多次换行输入多行内容，每次回车生成一个新的段落。"""
        body = self.enter_editor( driver )
        ActionChains( driver ).click( body ).perform()
        time.sleep( 0.3 )
        ActionChains( driver ).send_keys( lines[0] ).perform()
        for line in lines[1:]:
            ActionChains( driver ).key_down( Keys.ENTER ).key_up( Keys.ENTER ).perform()
            time.sleep( 0.2 )
            ActionChains( driver ).send_keys( line ).perform()
        time.sleep( 0.5 )
        self.leave_editor( driver )

    def select_all_text(self, driver):
        """在编辑区内按 Ctrl+A 选中全部正文内容。"""
        body = self.enter_editor( driver )
        ActionChains( driver ).click( body ).perform()
        body.send_keys( Keys.CONTROL, "a" )
        time.sleep( 0.5 )
        self.leave_editor( driver )

    def focus_paragraph(self, driver, index):
        """将光标定位到编辑区第 index 个段落（从 0 开始计数，段落含标题行）。"""
        body = self.enter_editor( driver )
        paragraphs = body.find_elements(
            By.XPATH,
            "./*[self::p or self::h1 or self::h2 or self::h3 or self::h4 or self::h5 or self::h6"
            " or self::ol or self::ul or self::table or self::div]" )
        ActionChains( driver ).click( paragraphs[index] ).perform()
        time.sleep( 0.4 )
        self.leave_editor( driver )

    def open_menu(self, driver, menu_name):
        """展开菜单栏中指定名称的菜单。"""
        self.leave_editor( driver )
        driver.find_element( By.TAG_NAME, "body" ).send_keys( Keys.ESCAPE )
        time.sleep( 0.3 )
        menu = driver.find_element(
            By.XPATH, "//button[contains(@class,'tox-mbtn')][normalize-space(.)='%s']" % menu_name )
        menu.click()
        time.sleep( 0.6 )

    def click_item(self, driver, text, exact=False):
        """点击已展开的菜单/下拉框中的菜单项。"""
        condition = "normalize-space(.)='%s'" % text if exact else "contains(normalize-space(.),'%s')" % text
        item = WebDriverWait( driver, 10 ).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//div[contains(@class,'tox-collection__item')][%s]" % condition) ) )
        item.click()
        time.sleep( 0.4 )

    def choose_dropdown(self, driver, aria_label, option_text):
        """点击工具栏下拉框（字体 / 字体大小 / 段落样式）并选择列表中的某一项。"""
        self.leave_editor( driver )
        dropdown = driver.find_element(
            By.CSS_SELECTOR, ".tox-tbtn--select[aria-label='%s']" % aria_label )
        dropdown.click()
        time.sleep( 0.8 )
        self.click_item( driver, option_text, exact=True )

    def click_toolbar_button(self, driver, aria_label):
        """点击工具栏中带指定名称的按钮（粗体、斜体、下划线、删除线、居中对齐等）。"""
        self.leave_editor( driver )
        button = driver.find_element( By.CSS_SELECTOR, ".tox-tbtn[aria-label='%s']" % aria_label )
        button.click()
        time.sleep( 0.5 )

    def click_list_button(self, driver, ordered=True):
        """点击工具栏【有序列表】或【无序列表】按钮。

        工具栏为 floating 模式，窗口宽度不足时这两个按钮会被收纳到工具栏最右侧的
        【更多...】面板中，因此先尝试直接点击，找不到时再展开【更多...】面板点击。
        """
        self.leave_editor( driver )
        aria_label = "有序列表" if ordered else "无序列表"
        for button in driver.find_elements( By.CSS_SELECTOR, ".tox-tbtn[aria-label='%s']" % aria_label ):
            if button.is_displayed():
                button.click()
                time.sleep( 0.6 )
                return
        groups = [ group for group in driver.find_elements(
            By.CSS_SELECTOR, ".tox-toolbar__overflow .tox-toolbar__group" ) if group.is_displayed() ]
        if not groups:
            driver.find_element( By.CSS_SELECTOR, ".tox-tbtn[aria-label='更多...']" ).click()
            time.sleep( 1 )
            groups = [ group for group in driver.find_elements(
                By.CSS_SELECTOR, ".tox-toolbar__overflow .tox-toolbar__group" ) if group.is_displayed() ]
        buttons = groups[0].find_elements( By.CSS_SELECTOR, ".tox-tbtn:not(.tox-split-button__chevron)" )
        buttons[0 if ordered else 1].click()
        time.sleep( 0.6 )

    def wait_dialog(self, driver):
        WebDriverWait( driver, 15 ).until(
            EC.visibility_of_element_located( (By.CSS_SELECTOR, ".tox-dialog") ) )
        time.sleep( 1 )

    def click_dialog_button(self, driver, text):
        button = driver.find_element(
            By.XPATH, "//div[contains(@class,'tox-dialog')]//button[normalize-space(.)='%s']" % text )
        button.click()
        time.sleep( 0.6 )

    def fill_dialog_field(self, driver, label, value):
        """按对话框中的字段名称定位输入框并填入内容。"""
        label_element = driver.find_element(
            By.XPATH, "//div[contains(@class,'tox-dialog')]//label[normalize-space(.)='%s']" % label )
        field = driver.find_element( By.ID, label_element.get_attribute( "for" ) )
        field.clear()
        field.send_keys( value )
        time.sleep( 0.2 )

    def dialog_field_value(self, driver, label):
        """读取对话框中某个字段当前的值。"""
        label_element = driver.find_element(
            By.XPATH, "//div[contains(@class,'tox-dialog')]//label[normalize-space(.)='%s']" % label )
        return driver.find_element( By.ID, label_element.get_attribute( "for" ) ).get_attribute( "value" )

    def set_dialog_field(self, driver, label, value, retry=3):
        """填入字段并校验，避免图片加载完成时把已填写的宽高改回原始尺寸。"""
        for _ in range( retry ):
            self.fill_dialog_field( driver, label, value )
            if self.dialog_field_value( driver, label ) == value:
                return
            time.sleep( 0.8 )
        raise AssertionError( "对话框字段【%s】未能设置为 %s" % ( label, value ) )

    def choose_dialog_list(self, driver, label, option_text):
        """点击对话框中下拉按钮（如【边框样式】【链接打开位置】）并选择选项。"""
        label_element = driver.find_element(
            By.XPATH, "//div[contains(@class,'tox-dialog')]//label[normalize-space(.)='%s']" % label )
        driver.find_element( By.ID, label_element.get_attribute( "for" ) ).click()
        time.sleep( 0.8 )
        self.click_item( driver, option_text, exact=True )

    def switch_dialog_tab(self, driver, tab_name):
        driver.find_element(
            By.XPATH,
            "//div[contains(@class,'tox-dialog')]//div[contains(@class,'tox-tab')][normalize-space(.)='%s']"
            % tab_name ).click()
        time.sleep( 1 )

    def close_dialog(self, driver):
        driver.find_element(
            By.CSS_SELECTOR, ".tox-dialog__header button, .tox-dialog__close" ).click()
        time.sleep( 0.8 )

    def insert_table(self, driver, columns, rows):
        """通过【表格】菜单的网格选择器插入指定列数与行数的表格。"""
        self.open_menu( driver, "表格" )
        self.click_item( driver, "表格", exact=True )
        time.sleep( 1.2 )
        cells = driver.find_elements(
            By.CSS_SELECTOR,
            ".tox-insert-table-picker > div[role='button']:not(.tox-insert-table-picker__selected)" )
        expect = "%dx%d" % ( columns, rows )
        for cell in cells:
            ActionChains( driver ).move_to_element( cell ).perform()
            time.sleep( 0.08 )
            label = driver.execute_script(
                "var el = document.querySelector('.tox-insert-table-picker__label');"
                "return el ? el.innerText : null;" )
            if label and label.strip().replace( "×", "x" ) == expect:
                cell.click()
                time.sleep( 1.5 )
                return
        raise AssertionError( "未能在表格网格选择器中选中 %s 的表格" % expect )

    def select_first_row_cells(self, driver):
        """按住鼠标左键从首行第一格拖动到首行最后一格，选中首行全部单元格。"""
        self.enter_editor( driver )
        cells = driver.find_elements( By.CSS_SELECTOR, "table tr:nth-child(1) td" )
        actions = ActionChains( driver )
        actions.click_and_hold( cells[0] )
        for cell in cells[1:]:
            actions.move_to_element( cell ).pause( 0.15 )
        actions.pause( 0.2 ).release().perform()
        time.sleep( 0.6 )
        self.leave_editor( driver )

    def select_table_cells(self, driver):
        """拖动鼠标跨单元格选中整个表格的内容，用于对表格文字统一设置对齐方式。"""
        self.enter_editor( driver )
        cells = driver.find_elements( By.CSS_SELECTOR, "table td" )
        actions = ActionChains( driver )
        actions.click_and_hold( cells[0] ).pause( 0.2 )
        for cell in cells[1:]:
            actions.move_to_element( cell ).pause( 0.1 )
        actions.pause( 0.2 ).release().perform()
        time.sleep( 0.6 )
        self.leave_editor( driver )

    def merge_first_row(self, driver):
        """在首行选中区域上点右键，悬浮到【单元格】，点击【合并单元格】。"""
        self.enter_editor( driver )
        cell = driver.find_elements( By.CSS_SELECTOR, "table tr:nth-child(1) td" )[0]
        ActionChains( driver ).context_click( cell ).perform()
        time.sleep( 1.2 )
        self.leave_editor( driver )
        submenu = driver.find_element(
            By.XPATH, "//div[contains(@class,'tox-collection__item')][normalize-space(.)='单元格']" )
        ActionChains( driver ).move_to_element( submenu ).perform()
        time.sleep( 1.2 )
        for item in driver.find_elements(
                By.XPATH, "//div[contains(@class,'tox-collection__item')][normalize-space(.)='合并单元格']" ):
            if "state-disabled" not in ( item.get_attribute( "class" ) or "" ):
                item.click()
                time.sleep( 1.5 )
                return
        raise AssertionError( "【合并单元格】菜单项不可用，首行单元格未能选中" )

    def fill_table(self, driver, row_texts):
        """依次点击表格各单元格并输入文本。"""
        self.enter_editor( driver )
        for row_index, texts in enumerate( row_texts ):
            cells = driver.find_elements(
                By.CSS_SELECTOR, "table tr:nth-child(%d) td" % ( row_index + 1 ) )
            for cell, text in zip( cells, texts ):
                ActionChains( driver ).click( cell ).send_keys( text ).perform()
                time.sleep( 0.3 )
        self.leave_editor( driver )

    def choose_text_color(self, driver, color_name):
        """【格式】→【文本颜色】→ 在颜色面板中点击指定颜色色块。"""
        self.open_menu( driver, "格式" )
        color_item = driver.find_element(
            By.XPATH, "//div[contains(@class,'tox-collection__item')][normalize-space(.)='文本颜色']" )
        ActionChains( driver ).move_to_element( color_item ).perform()
        time.sleep( 1.2 )
        swatch = WebDriverWait( driver, 10 ).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//div[contains(@class,'tox-swatch')][@title='%s']" % color_name) ) )
        swatch.click()
        time.sleep( 0.8 )

    def screenshot(self, driver, case_id):
        TestUutool.take_screenshot( driver, case_id + ".png" )

    def collapse_selection(self, driver, inside_text=True):
        """收起选区与弹出面板，并把光标重新定位，避免截图被选中高亮或链接高亮遮挡。

        inside_text 为 True 时光标落到正文文字中间，工具栏按钮状态随文字格式更新；
        为 False 时光标落到段落末尾的格式元素之外，用于链接等不希望出现高亮的场景。
        """
        self.leave_editor( driver )
        for more_button in driver.find_elements( By.CSS_SELECTOR, ".tox-tbtn[aria-label='更多...']" ):
            if more_button.get_attribute( "aria-expanded" ) == "true":
                more_button.click()
                time.sleep( 0.5 )
        driver.find_element( By.TAG_NAME, "body" ).send_keys( Keys.ESCAPE )
        time.sleep( 0.3 )
        if inside_text:
            driver.execute_script(
                "var ed = window.tinymce && window.tinymce.activeEditor;"
                "if (!ed) { return; }"
                "function firstText(node) {"
                "  if (node.nodeType === 3 && node.nodeValue.trim()) { return node; }"
                "  for (var i = 0; i < node.childNodes.length; i++) {"
                "    var found = firstText(node.childNodes[i]);"
                "    if (found) { return found; }"
                "  }"
                "  return null;"
                "}"
                "var text = firstText(ed.getBody());"
                "if (!text) { return; }"
                "var rng = ed.dom.createRng();"
                "rng.setStart(text, Math.min(2, text.nodeValue.length));"
                "rng.collapse(true);"
                "ed.selection.setRng(rng);"
                "ed.focus();" )
        else:
            driver.execute_script(
                "var ed = window.tinymce && window.tinymce.activeEditor;"
                "if (!ed) { return; }"
                "var body = ed.getBody();"
                "var last = body.lastChild;"
                "if (!last) { return; }"
                "var rng = ed.dom.createRng();"
                "rng.setStart(last, last.childNodes.length);"
                "rng.collapse(true);"
                "ed.selection.setRng(rng);"
                "ed.focus();" )
        time.sleep( 0.6 )

    # ------------------------------------------------------------------
    # 二、测试用例
    # ------------------------------------------------------------------
    def test_Uutool_R001(self, driver):
        """R001：两行内容分别设置为一级标题、二级标题，并打开预览查看效果（共 4 条用例）。"""
        cases = [
            ( "Uutool_R001_001", "Web应用测试", "个人赛" ),
            ( "Uutool_R001_002", "Web应用测试", "团队赛" ),
            ( "Uutool_R001_003", "开发者测试", "个人赛" ),
            ( "Uutool_R001_004", "开发者测试", "团队赛" ),
        ]
        for case_id, first_line, second_line in cases:
            self.open_editor( driver )
            self.type_lines( driver, [ first_line, second_line ] )
            self.focus_paragraph( driver, 0 )
            self.choose_dropdown( driver, "样式", "一级标题" )
            self.focus_paragraph( driver, 1 )
            self.choose_dropdown( driver, "样式", "二级标题" )
            self.open_menu( driver, "查看" )
            self.click_item( driver, "预览", exact=True )
            self.wait_dialog( driver )
            time.sleep( 1 )
            self.screenshot( driver, case_id )

    def test_Uutool_R002(self, driver):
        """R002：选中全部正文，依次叠加【粗体】【斜体】【下划线】【删除线】四种格式（共 2 条用例）。"""
        cases = [ ( "Uutool_R002_001", "全国大学生软件测试大赛" ),
                  ( "Uutool_R002_002", "慕测平台" ) ]
        for case_id, content in cases:
            self.open_editor( driver )
            self.type_lines( driver, [ content ] )
            for aria_label in [ "粗体", "斜体", "下划线", "删除线" ]:
                self.select_all_text( driver )
                self.click_toolbar_button( driver, aria_label )
            time.sleep( 0.5 )
            self.collapse_selection( driver )
            self.screenshot( driver, case_id )

    def test_Uutool_R003(self, driver):
        """R003：第一行设置有序列表、第二行设置无序列表（共 2 条用例）。"""
        cases = [ ( "Uutool_R003_001", "Java代码" ),
                  ( "Uutool_R003_002", "Python代码" ) ]
        for case_id, second_line in cases:
            self.open_editor( driver )
            self.type_lines( driver, [ "Web应用测试", second_line ] )
            self.focus_paragraph( driver, 0 )
            self.click_list_button( driver, ordered=True )
            self.focus_paragraph( driver, 1 )
            self.click_list_button( driver, ordered=False )
            time.sleep( 0.8 )
            self.collapse_selection( driver )
            self.screenshot( driver, case_id )

    def test_Uutool_R004(self, driver):
        """R004：正文设置为 Arial Black 字体、18pt 字号（共 1 条用例）。"""
        self.open_editor( driver )
        self.type_lines( driver, [ "全国大学生软件测试大赛" ] )
        self.select_all_text( driver )
        self.choose_dropdown( driver, "字体", "Arial Black" )
        self.select_all_text( driver )
        self.choose_dropdown( driver, "字体大小", "18pt" )
        time.sleep( 0.8 )
        self.collapse_selection( driver )
        self.screenshot( driver, "Uutool_R004_001" )

    def test_Uutool_R005(self, driver):
        """R005：正文“慕测平台”插入指向 http://www.mooctest.net/#/login 的链接（共 1 条用例）。"""
        self.open_editor( driver )
        self.type_lines( driver, [ "慕测平台" ] )
        self.select_all_text( driver )
        self.open_menu( driver, "插入" )
        self.click_item( driver, "链接" )
        self.wait_dialog( driver )
        self.fill_dialog_field( driver, "地址", "http://www.mooctest.net/#/login" )
        self.click_dialog_button( driver, "保存" )
        time.sleep( 1 )
        self.collapse_selection( driver, inside_text=False )
        self.screenshot( driver, "Uutool_R005_001" )

    def test_Uutool_R006(self, driver):
        """R006：插入 3 行 4 列表格，首行合并单元格后填写内容并居中（共 1 条用例）。"""
        self.open_editor( driver )
        self.insert_table( driver, columns=4, rows=3 )
        self.select_first_row_cells( driver )
        self.merge_first_row( driver )
        self.fill_table( driver, [
            [ "Selenium操作" ],
            [ "浏览器Cookie管理", "点击鼠标右键", "鼠标移动到某个坐标", "全选" ],
            [ "driver.manage().addCookie()", "contextClick()", "moveByOffset()", '(Keys.CONTROL,"a")' ],
        ] )
        self.select_table_cells( driver )
        self.click_toolbar_button( driver, "居中对齐" )
        time.sleep( 1 )
        self.screenshot( driver, "Uutool_R006_001" )

    def test_Uutool_R007(self, driver):
        """R007：插入带替代描述、固定宽高、间距与实线边框的图片（共 1 条用例）。"""
        self.open_editor( driver )
        self.type_lines( driver, [ "慕测平台Logo示例：" ] )
        self.open_menu( driver, "插入" )
        self.click_item( driver, "图片" )
        self.wait_dialog( driver )
        self.fill_dialog_field( driver, "源", "https://www.mooctest.net/img/logo.a000b55f.jpg" )
        self.fill_dialog_field( driver, "替代描述", "慕测平台Logo" )
        time.sleep( 3 )
        driver.find_element( By.CSS_SELECTOR, ".tox-dialog .tox-lock" ).click()
        time.sleep( 0.5 )
        self.set_dialog_field( driver, "宽度", "200" )
        self.set_dialog_field( driver, "高度", "200" )
        self.switch_dialog_tab( driver, "高级" )
        self.set_dialog_field( driver, "垂直间距", "10" )
        self.set_dialog_field( driver, "水平间距", "10" )
        self.set_dialog_field( driver, "边框宽度", "2" )
        self.choose_dialog_list( driver, "边框样式", "实线" )
        self.click_dialog_button( driver, "保存" )
        time.sleep( 3 )
        self.scroll_to_editor( driver )
        self.screenshot( driver, "Uutool_R007_001" )

    def test_Uutool_R008(self, driver):
        """R008：正文设置为代码格式并切换至源代码视图（共 1 条用例）。"""
        self.open_editor( driver )
        self.type_lines( driver, [ "Web应用测试" ] )
        self.select_all_text( driver )
        self.open_menu( driver, "格式" )
        self.click_item( driver, "代码", exact=True )
        time.sleep( 0.8 )
        self.open_menu( driver, "查看" )
        self.click_item( driver, "源代码", exact=True )
        self.wait_dialog( driver )
        time.sleep( 1 )
        self.screenshot( driver, "Uutool_R008_001" )

    def test_Uutool_R009(self, driver):
        """R009：点击【复制HTML】后点击【下载HTML】，保留操作提示与下载状态（共 1 条用例）。"""
        self.open_editor( driver )
        self.type_lines( driver, [ "全国大学生软件测试大赛" ] )
        self.leave_editor( driver )
        copy_button = driver.find_element( By.CSS_SELECTOR, ".js-copy" )
        driver.execute_script( "arguments[0].scrollIntoView({block: 'center'});", copy_button )
        time.sleep( 0.3 )
        copy_button.click()
        time.sleep( 0.8 )
        driver.find_element( By.CSS_SELECTOR, ".js-download" ).click()
        time.sleep( 0.3 )
        self.scroll_to_editor( driver )
        self.screenshot( driver, "Uutool_R009_001" )

    def test_Uutool_R010(self, driver):
        """R010：查找“测试”并全部替换为“比赛”（共 1 条用例）。"""
        self.open_editor( driver )
        self.type_lines( driver, [ "全国大学生软件测试大赛Web应用测试" ] )
        self.open_menu( driver, "编辑" )
        self.click_item( driver, "查找并替换" )
        self.wait_dialog( driver )
        find_input = driver.find_element(
            By.XPATH, "//div[contains(@class,'tox-dialog')]//input[@placeholder='寻找']" )
        replace_input = driver.find_element(
            By.XPATH, "//div[contains(@class,'tox-dialog')]//input[@placeholder='替换为']" )
        find_input.clear()
        find_input.send_keys( "测试" )
        replace_input.clear()
        replace_input.send_keys( "比赛" )
        time.sleep( 0.3 )
        self.click_dialog_button( driver, "寻找" )
        time.sleep( 0.5 )
        self.click_dialog_button( driver, "替换全部" )
        time.sleep( 0.5 )
        self.close_dialog( driver )
        self.scroll_to_editor( driver )
        time.sleep( 0.5 )
        self.screenshot( driver, "Uutool_R010_001" )

    def test_Uutool_R011(self, driver):
        """R011：选中正文，通过【格式】→【文本颜色】设置为红色（共 1 条用例）。"""
        self.open_editor( driver )
        self.type_lines( driver, [ "全国大学生软件测试大赛" ] )
        self.select_all_text( driver )
        self.choose_text_color( driver, "红色" )
        time.sleep( 0.8 )
        self.collapse_selection( driver )
        self.screenshot( driver, "Uutool_R011_001" )

    # test-code-end

    @staticmethod
    def take_screenshot(driver, file_name):
        timestamp = datetime.now().strftime( "%H%M%S%d%f" )[:-3]
        timestamped_file_name = f"{timestamp}_{file_name}"
        screenshots_dir = "screenshots"
        if not os.path.exists( screenshots_dir ):
            os.makedirs( screenshots_dir )
        screenshot_file_path = os.path.join( screenshots_dir, timestamped_file_name )
        driver.save_screenshot( screenshot_file_path )
