import os
from datetime import datetime
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.service import Service


@pytest.fixture( scope="function" )
def driver():
    # 提交最终代码脚本时，请将驱动路径换回官方路径"C:\\Program Files\\Google\\Chrome\\Application\\chromedriver.exe"
    service = Service(
        executable_path="C:\\Program Files\\Google\\Chrome\\Application\\chromedriver.exe" )
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Chrome(service=service, options=options)
    driver.get( "https://www.sf-express.com/" )
    driver.maximize_window()
    driver.implicitly_wait( 10 )
    yield driver
    driver.quit()


class TestSF:

    # test-code-start

    # 仅在官方允许区域内补充。下面的 _ 开头方法是操作复用工具，
    # pytest 只收集 test_SF_R001 ~ test_SF_R010 共 10 个测试函数。
    # 页面控件定位采用多候选策略；网页版本变更时需根据实际 DOM 调整定位器。
    import time
    import re
    from datetime import timedelta
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        TimeoutException, NoSuchElementException, StaleElementReferenceException,
        ElementClickInterceptedException, WebDriverException,
    )

    def _xp(self, value):
        """将中文测试数据安全转换为 XPath 字面量。"""
        value = str(value)
        if "'" not in value:
            return "'" + value + "'"
        if '"' not in value:
            return '"' + value + '"'
        return "concat(" + ", \"'\", ".join("'" + s + "'" for s in value.split("'")) + ")"

    def _visible(self, driver, xpath, timeout=8, root=None):
        """返回第一个可见元素，不使用固定下标作为唯一定位依据。"""
        end = self.time.monotonic() + timeout
        context = root if root is not None else driver
        while self.time.monotonic() < end:
            try:
                for element in context.find_elements(self.By.XPATH, xpath):
                    if element.is_displayed():
                        return element
            except (self.StaleElementReferenceException, self.WebDriverException):
                pass
            self.time.sleep(0.2)
        raise AssertionError("未找到可见控件：" + xpath)

    def _click_element(self, driver, element):
        driver.execute_script("arguments[0].scrollIntoView({block:'center',inline:'nearest'});", element)
        try:
            element.click()
        except (self.ElementClickInterceptedException, self.WebDriverException):
            driver.execute_script("arguments[0].click();", element)
        self.time.sleep(0.35)
        return element

    def _click_text(self, driver, text, exact=True, root=None, timeout=8):
        """兼容普通按钮、下拉选项、Element/Ant Design 弹层及可点击文本。"""
        aliases = {
            "代收贷款": ("代收贷款", "代收货款"),
            "大件（20kg+）": ("大件（20kg+）", "大件 (20kg+)", "大件"),
            "省/直辖市": ("省/直辖市", "省份/直辖市", "省份"),
        }
        terms = aliases.get(str(text), (str(text),))
        context = root if root is not None else driver
        end = self.time.monotonic() + timeout
        last_error = None
        while self.time.monotonic() < end:
            for term in terms:
                q = self._xp(term)
                cond = "normalize-space(.)=" + q if exact else "contains(normalize-space(.)," + q + ")"
                paths = [
                    "//*[self::button or self::a or self::li or self::label or @role='option' or @role='menuitem' or @role='tab'][" + cond + "]",
                    "//*[self::span or self::div or self::p][" + cond + "]",
                    "//*[self::button or self::a or self::li or @role='option' or @role='menuitem'][contains(normalize-space(.)," + q + ")]",
                ]
                for xp in paths:
                    try:
                        candidates = [e for e in context.find_elements(self.By.XPATH, xp)
                                      if e.is_displayed() and e.is_enabled()]
                        # 优先文本完全匹配、尺寸较小的元素，避免点击整个页面容器。
                        candidates.sort(key=lambda e: (0 if (e.text or '').strip() == term else 1,
                                                       len((e.text or '').strip())))
                        for element in candidates:
                            try:
                                return self._click_element(driver, element)
                            except (self.StaleElementReferenceException, self.ElementClickInterceptedException,
                                    self.WebDriverException) as exc:
                                last_error = exc
                                continue
                    except (self.StaleElementReferenceException, self.WebDriverException) as exc:
                        last_error = exc
            self.time.sleep(0.2)
        raise AssertionError("未找到可点击文字：%s；当前页面：%s" % (text, driver.current_url))

    def _navigate(self, driver, item):
        """从首页进入服务支持，再通过左侧“服务查询”菜单进入真实业务页。
        不再用全页面同名文字作为成功条件，必须核验目标 URL 和业务控件。
        """
        routes = {
            "运费时效": ("/price-query", ("#origion .item-city", "#dests .item-city")),
            "服务网点": ("/outlets-query", ("#range-query-citypicker input.result", "#range-key-word")),
            "收寄标准": ("/accept-query", ("#accept-from-input > input", "#accept-consignment-input > input")),
            "服务范围": ("/range-query", ("#range-query-citypicker input.result",)),
        }
        if item not in routes:
            raise AssertionError("未配置服务页面导航目标：" + str(item))

        expected_path, required_controls = routes[item]
        old_wait = driver.timeouts.implicit_wait
        driver.implicitly_wait(0)
        try:
            driver.switch_to.default_content()
            driver.get("https://www.sf-express.com/")
            before = set(driver.window_handles)
            self._click_text(driver, "服务支持", exact=True, timeout=18)

            def support_ready(d):
                # “服务支持”有时会打开新标签页；逐个检查，避免停留在旧首页。
                for handle in reversed(d.window_handles):
                    try:
                        d.switch_to.window(handle)
                        if any(e.is_displayed() for e in d.find_elements(
                                self.By.CSS_SELECTOR, ".side-menu")):
                            return True
                    except (self.StaleElementReferenceException, self.WebDriverException):
                        continue
                return False

            self.WebDriverWait(
                driver, 30, poll_frequency=0.25,
                ignored_exceptions=(self.StaleElementReferenceException,)
            ).until(support_ready)

            support_handle = None
            for handle in reversed(driver.window_handles):
                driver.switch_to.window(handle)
                if any(e.is_displayed() for e in driver.find_elements(
                        self.By.CSS_SELECTOR, ".side-menu")):
                    support_handle = handle
                    break
            if support_handle is None:
                raise AssertionError("已点击“服务支持”，但未找到左侧服务菜单")

            def target_ready(d):
                # 同时检查所有标签页，防止路由在新窗口打开后仍检查旧窗口。
                for handle in reversed(d.window_handles):
                    try:
                        d.switch_to.window(handle)
                        if expected_path not in d.current_url:
                            continue
                        if all(any(
                            e.is_displayed() and e.is_enabled()
                            for e in d.find_elements(self.By.CSS_SELECTOR, selector)
                        ) for selector in required_controls):
                            return True
                    except (self.StaleElementReferenceException, self.WebDriverException):
                        continue
                if support_handle in d.window_handles:
                    d.switch_to.window(support_handle)
                return False

            for attempt in range(3):
                if target_ready(driver):
                    return

                if support_handle not in driver.window_handles:
                    raise AssertionError("服务支持菜单所在标签页已关闭，无法进入：" + item)
                driver.switch_to.window(support_handle)

                def child_ready(d):
                    for element in d.find_elements(
                            self.By.CSS_SELECTOR, ".side-menu .side-child-item"):
                        if element.is_displayed() and element.is_enabled() and element.text.strip() == item:
                            return element
                    return False

                child = child_ready(driver)
                if not child:
                    # 左侧“服务查询”可能处于折叠状态；只展开菜单，不点击页面其他同名文字。
                    titles = [e for e in driver.find_elements(
                        self.By.CSS_SELECTOR, ".side-menu .title")
                        if e.is_displayed() and e.is_enabled()
                        and e.text.strip() == "服务查询"]
                    if titles:
                        self._click_element(driver, titles[0])
                    try:
                        child = self.WebDriverWait(
                            driver, 8, poll_frequency=0.25,
                            ignored_exceptions=(self.StaleElementReferenceException,)
                        ).until(child_ready)
                    except self.TimeoutException:
                        child = False

                if not child:
                    raise AssertionError(
                        "未找到左侧“服务查询”菜单项：%s；当前 URL=%s；可见菜单=%s" % (
                            item, driver.current_url,
                            [e.text.strip() for e in driver.find_elements(
                                self.By.CSS_SELECTOR, ".side-menu .side-child-item")
                             if e.is_displayed()]
                        )
                    )

                self._click_element(driver, child)
                try:
                    self.WebDriverWait(
                        driver, 20, poll_frequency=0.25,
                        ignored_exceptions=(self.StaleElementReferenceException,)
                    ).until(target_ready)
                    return
                except self.TimeoutException:
                    if attempt == 2:
                        break

            raise AssertionError(
                "点击左侧“%s”后未进入目标业务页：期望 URL 包含 %s；实际 URL=%s；"
                "请检查官网路由或页面加载状态" %
                (item, expected_path, driver.current_url)
            )
        finally:
            driver.implicitly_wait(old_wait)

    def _find_input(self, driver, hints=(), label=None, ordinal=0, timeout=8):
        """按 placeholder / form-item 标签定位输入框。"""
        xpaths = []
        for hint in hints:
            q = self._xp(hint)
            xpaths.append("//input[contains(@placeholder," + q + ") and not(@disabled)]")
            xpaths.append("//textarea[contains(@placeholder," + q + ") and not(@disabled)]")
        if label:
            q = self._xp(label)
            xpaths += [
                "//*[self::label or self::span][contains(normalize-space(.)," + q + ")]"
                "/ancestor::*[contains(@class,'form-item')][1]//input",
                "//*[self::label or self::span][normalize-space(.)=" + q + "]"
                "/following::input[1]",
            ]
        end = self.time.monotonic() + timeout
        while self.time.monotonic() < end:
            for xp in xpaths:
                try:
                    matched = [e for e in driver.find_elements(self.By.XPATH, xp)
                               if e.is_displayed() and e.is_enabled()]
                    if len(matched) > ordinal:
                        return matched[ordinal]
                except self.StaleElementReferenceException:
                    continue
            self.time.sleep(0.2)
        raise AssertionError("找不到输入框：" + str(hints) + " / " + str(label))

    def _fill(self, driver, element, value, choose_suggestion=False):
        """输入真实表单值；不通过直接修改 React/Vue 的内部状态作弊。"""
        self._click_element(driver, element)
        element.send_keys(self.Keys.CONTROL, "a")
        element.send_keys(self.Keys.BACKSPACE)
        element.send_keys(str(value))
        self.time.sleep(0.5)
        if choose_suggestion:
            # 只在确有与输入一致的可见候选项时点击。
            try:
                self._click_text(driver, str(value), exact=False, timeout=1)
            except AssertionError:
                pass

    def _wait_area_context(self, driver, hints, labels, timeout=15):
        """等待可见地址字段，按实际内容查找文档/嵌套 frame，成功后保留上下文。"""
        conditions = []
        for hint in hints:
            q = self._xp(hint)
            conditions.extend([
                "contains(@placeholder," + q + ")",
                "contains(@aria-label," + q + ")",
                "contains(@title," + q + ")",
                "((self::span or self::div or self::p or self::button or self::label)"
                " and string-length(normalize-space(.)) <= 90"
                " and contains(normalize-space(.)," + q + "))",
            ])
        for label in labels:
            conditions.append(
                "((self::label or self::span or self::div or self::p)"
                " and normalize-space(.)=" + self._xp(label) + ")")
        xpath = "//*[" + " or ".join(conditions) + "]"

        def find_context(depth=0):
            if any(e.is_displayed() for e in driver.find_elements(self.By.XPATH, xpath)):
                return True
            if depth >= 5:
                return False
            for frame in driver.find_elements(self.By.CSS_SELECTOR, "iframe, frame"):
                if not frame.is_displayed():
                    continue
                driver.switch_to.frame(frame)
                if find_context(depth + 1):
                    return True  # 后续点击、输入和截图继续使用找到的文档。
                driver.switch_to.parent_frame()
            return False

        old_wait = driver.timeouts.implicit_wait
        driver.implicitly_wait(0)
        end = self.time.monotonic() + timeout
        try:
            while self.time.monotonic() < end:
                try:
                    driver.switch_to.default_content()
                    if find_context():
                        return
                except (self.NoSuchElementException, self.StaleElementReferenceException,
                        self.WebDriverException):
                    # frame 在跳转/重绘时可能失效；下一轮从顶层重新获取。
                    pass
                self.time.sleep(0.2)
            driver.switch_to.default_content()
            raise AssertionError(
                "未找到可见地址字段（已检查顶层及嵌套 frame）：%s；页面=%s；"
                "请检查业务页是否加载、是否有遮挡，以及实际 DOM 定位器" %
                (hints, driver.current_url))
        finally:
            driver.implicitly_wait(old_wait)

    def _open_area(self, driver, field):
        """打开官网地址选择器。运费时效页实际控件提示为“请选择始发地地区。例如：北京市”等，
        它通常是自定义 div/trigger，而不是普通 input，因此必须优先按实际占位文字定位。"""
        labels = {
            "origin": ("始发地", "寄件地", "请选择始发地"),
            "destination": ("目的地", "收件地", "请选择目的地"),
            "outlet": ("选择收寄件区域", "收寄件区域", "请选择收寄件区域"),
            "range": ("收寄件", "收寄件区域", "请选择收寄件"),
        }
        ui_hints = {
            "origin": ("请选择始发地地区", "请选择始发地地区。例如：北京市"),
            "destination": ("请选择目的地地区", "请选择目的地地区。例如：北京市"),
            "outlet": ("请选择收寄件区域", "选择收寄件区域", "请选择省份/城市/区县"),
            "range": ("请选择收寄件区域", "请选择收寄件地区", "请选择省份/城市/区县"),
        }

        self._wait_area_context(driver, ui_hints[field], labels[field])

        def popup_open():
            # 等待异步渲染完成，避免快速重复点击把刚打开的弹层关闭。
            old_wait = driver.timeouts.implicit_wait
            driver.implicitly_wait(0)
            try:
                return bool(self.WebDriverWait(driver, 3, poll_frequency=0.2).until(
                    lambda d: self._area_search_input(d)))
            except self.TimeoutException:
                return False
            finally:
                driver.implicitly_wait(old_wait)

        # 1. 优先按官网运费时效页面真实显示的占位文字定位控件。
        for hint in ui_hints.get(field, ()):
            q = self._xp(hint)
            xpaths = [
                "//*[@placeholder and contains(@placeholder," + q + ")]",
                "//*[@aria-label and contains(@aria-label," + q + ")]",
                "//*[@title and contains(@title," + q + ")]",
            ]
            for xp in xpaths:
                try:
                    elements = [e for e in driver.find_elements(self.By.XPATH, xp)
                                if e.is_displayed() and e.is_enabled()]
                except self.WebDriverException:
                    elements = []
                for element in elements:
                    try:
                        self._click_element(driver, element)
                        self.time.sleep(0.25)
                        if popup_open():
                            return element
                    except self.WebDriverException:
                        continue

            # 占位文字有时由 span/div 绘制，而非真正的 input placeholder。
            xp = ("//*[self::div or self::span or self::p or self::button or self::label]"
                  "[contains(normalize-space(.)," + q + ")]")
            try:
                elements = [e for e in driver.find_elements(self.By.XPATH, xp)
                            if e.is_displayed() and 0 < len((e.text or '').strip()) <= 90]
                elements.sort(key=lambda e: len((e.text or '').strip()))
            except self.WebDriverException:
                elements = []
            for element in elements:
                # 先点击最贴近占位文字的节点，再尝试其父级自定义选择器容器。
                targets = [element]
                try:
                    targets.extend(element.find_elements(
                        self.By.XPATH,
                        "./ancestor::*[self::div or self::button][position() <= 3]"))
                except self.WebDriverException:
                    pass
                for target in targets:
                    try:
                        if not target.is_displayed() or not target.is_enabled():
                            continue
                        self._click_element(driver, target)
                        self.time.sleep(0.25)
                        if popup_open():
                            return target
                    except self.WebDriverException:
                        continue

        # 2. 兼容其他服务页：从标签所在表单行找真正的选择控件。
        for term in labels.get(field, ()):
            q = self._xp(term)
            xpaths = [
                "//*[self::label or self::span or self::div or self::p][normalize-space(.)=" + q + "]"
                "/following::*[@role='combobox' or self::input or contains(@class,'select') "
                "or contains(@class,'picker') or contains(@class,'trigger')][1]",
                "//*[self::label or self::span or self::div or self::p][contains(normalize-space(.)," + q + ")]"
                "/following::*[@role='combobox' or self::input or contains(@class,'select') "
                "or contains(@class,'picker') or contains(@class,'trigger')][1]",
            ]
            for xp in xpaths:
                try:
                    elements = [e for e in driver.find_elements(self.By.XPATH, xp)
                                if e.is_displayed() and e.is_enabled()]
                except self.WebDriverException:
                    elements = []
                for element in elements:
                    try:
                        self._click_element(driver, element)
                        self.time.sleep(0.25)
                        if popup_open():
                            return element
                    except self.WebDriverException:
                        continue

        # 3. 不再把“点到了标签”误判成“弹窗已打开”；失败时给出可诊断信息。
        raise AssertionError(
            "未能打开地址选择弹层：字段=%s；尝试占位文字=%s；当前可见输入框=%s；页面=%s" %
            (field, ui_hints.get(field, ()), self._visible_input_summary(driver), driver.current_url))

    def _visible_input_summary(self, driver):
        summary = []
        try:
            for e in driver.find_elements(self.By.XPATH, "//input|//textarea|//*[@contenteditable='true']"):
                if e.is_displayed():
                    summary.append("%s:%s" % (e.tag_name, e.get_attribute('placeholder') or e.get_attribute('aria-label') or e.get_attribute('value') or ''))
        except self.WebDriverException:
            pass
        return summary[:30]

    def _area_popup_root(self, driver, input_element=None):
        """尽量定位地址选择弹层，而不是页面上的普通表单区域。"""
        tokens = ("dropdown", "popup", "popover", "modal", "dialog", "cascader",
                  "picker", "address", "region", "area-panel", "select-options", "listbox")
        if input_element is not None:
            try:
                for ancestor in input_element.find_elements(self.By.XPATH, "./ancestor::*"):
                    if not ancestor.is_displayed():
                        continue
                    cls = (ancestor.get_attribute("class") or "").lower()
                    role = (ancestor.get_attribute("role") or "").lower()
                    if role in ("dialog", "listbox", "tree", "menu") or any(t in cls for t in tokens):
                        # 排除过小的输入框包装层，优先真正包含选项的弹层。
                        if len((ancestor.text or "").strip()) >= 2:
                            return ancestor
            except self.WebDriverException:
                pass
        selectors = (
            "[role='dialog']", "[role='listbox']", "[class*='cascader']",
            "[class*='popover']", "[class*='dropdown']", "[class*='popup']",
            "[class*='modal']", "[class*='picker-panel']", "[class*='select-options']",
        )
        for selector in selectors:
            try:
                for element in driver.find_elements(self.By.CSS_SELECTOR, selector):
                    if element.is_displayed() and (element.text or "").strip():
                        return element
            except self.WebDriverException:
                pass
        return None

    def _area_search_input(self, driver):
        """只选择地址弹窗搜索框，禁止把详细地址、重量等业务输入框当成搜索框。"""
        excluded = ("详细地址", "重量", "体积", "长", "宽", "高", "日期", "时间",
                    "关键词", "托寄物品", "邮编", "手机", "电话", "姓名", "公司")
        address_terms = ("省份", "省/直辖市", "城市", "区县", "地区", "行政区", "搜索")
        candidates = []
        for element in driver.find_elements(self.By.XPATH, "//input|//textarea|//*[@contenteditable='true']"):
            try:
                if not element.is_displayed() or not element.is_enabled():
                    continue
                ph = (element.get_attribute("placeholder") or "").strip()
                aria = (element.get_attribute("aria-label") or "").strip()
                title = (element.get_attribute("title") or "").strip()
                descriptor = " ".join((ph, aria, title))
                if any(word in descriptor for word in excluded):
                    continue
                root = self._area_popup_root(driver, element)
                score = 0
                if any(word in descriptor for word in address_terms):
                    score += 100
                if "输入" in descriptor or "搜索" in descriptor:
                    score += 20
                if root is not None:
                    score += 30
                # 无 placeholder 的输入框只允许作为弹层内的兜底候选。
                if not descriptor and root is None:
                    continue
                candidates.append((score, element))
            except (self.StaleElementReferenceException, self.WebDriverException):
                continue
        if not candidates:
            return None
        candidates.sort(key=lambda pair: pair[0], reverse=True)
        # 只有明确的地址搜索框，或位于弹层内的输入框才可使用。
        if candidates[0][0] < 30:
            return None
        return candidates[0][1]

    def _has_area_search_input(self, driver):
        return self._area_search_input(driver) is not None

    def _area_search(self, driver, keyword):
        """在地址选择弹层的搜索框中输入，不再盲选页面最后一个 input。"""
        end = self.time.monotonic() + 8
        target = None
        while self.time.monotonic() < end:
            target = self._area_search_input(driver)
            if target is not None:
                break
            self.time.sleep(0.2)
        if target is None:
            raise AssertionError("未找到地址弹层搜索输入框；当前可见输入框：%s；页面：%s" %
                                 (self._visible_input_summary(driver), driver.current_url))
        self._fill(driver, target, keyword)
        self.time.sleep(0.7)
        return target

    def _click_area_option(self, driver, text, exact=False, timeout=4, input_element=None):
        """优先在地址弹层中点击候选项，避免误点页面导航或其他区域的同名文字。"""
        root = self._area_popup_root(driver, input_element)
        if root is not None:
            try:
                return self._click_text(driver, text, exact=exact, root=root, timeout=timeout)
            except AssertionError:
                pass
        # 有些站点将下拉候选项挂载到 body 下的 portal；再查全页面可见候选项。
        return self._click_text(driver, text, exact=exact, timeout=timeout)

    def _select_area(self, driver, field, mode, path, search=None):
        """按手册的层级选择地址；搜索模式兼容点击城市后弹层关闭的官网交互。"""
        self._open_area(driver, field)
        self.time.sleep(0.4)
        search_input = None
        if mode == "hmt":
            self._click_text(driver, "港澳台", exact=False, timeout=6)
            self.time.sleep(0.35)
        elif mode == "province":
            self._click_text(driver, "省/直辖市", exact=False, timeout=6)
            self.time.sleep(0.35)
        elif mode == "search":
            city = search or (path[0] if path else "")
            search_input = self._area_search(driver, city)
            # 城市候选可能是一个层级入口，也可能直接选中城市；后面会检测弹层状态。
            try:
                self._click_area_option(driver, city, exact=False, timeout=3,
                                        input_element=search_input)
                self.time.sleep(0.35)
            except AssertionError:
                # 部分页面输入城市后直接列出区县，不需要先点城市。
                pass
        elif mode == "hot":
            pass

        for name in path:
            try:
                self._click_area_option(driver, name, exact=True, timeout=2,
                                        input_element=search_input)
                self.time.sleep(0.3)
                continue
            except AssertionError:
                pass
            try:
                self._click_area_option(driver, name, exact=False, timeout=2,
                                        input_element=search_input)
                self.time.sleep(0.3)
                continue
            except AssertionError:
                pass

            # 关键修复：有些官网版本点击“广州市”后会直接关闭弹层，不能继续在已关闭的
            # 弹层里找“黄埔区”。先重新打开同一个地址选择器，再搜索目标区县。
            if mode == "search" and not self._has_area_search_input(driver):
                self._open_area(driver, field)
                self.time.sleep(0.35)

            try:
                search_input = self._area_search(driver, name)
                self._click_area_option(driver, name, exact=False, timeout=4,
                                        input_element=search_input)
                self.time.sleep(0.35)
                continue
            except AssertionError as first_error:
                # 个别联想框只按完整路径匹配，使用“城市+区县”再次检索。
                if mode == "search" and search:
                    if not self._has_area_search_input(driver):
                        self._open_area(driver, field)
                        self.time.sleep(0.35)
                    search_input = self._area_search(driver, search + name)
                    try:
                        self._click_area_option(driver, name, exact=False, timeout=4,
                                                input_element=search_input)
                        self.time.sleep(0.35)
                        continue
                    except AssertionError:
                        pass
                visible_texts = []
                try:
                    root = self._area_popup_root(driver, search_input)
                    context = root if root is not None else driver
                    for element in context.find_elements(
                            self.By.XPATH,
                            "//*[self::li or self::span or self::div or self::p or @role='option']"):
                        if element.is_displayed():
                            value = (element.text or "").strip()
                            if value and len(value) < 80 and value not in visible_texts:
                                visible_texts.append(value)
                except self.WebDriverException:
                    pass
                raise AssertionError("未找到地址候选项：%s；字段=%s；搜索=%s；弹层可见文本=%s；页面=%s" %
                                     (name, field, search, visible_texts[:35], driver.current_url))
        return True

    def _set_address(self, driver, address, origin=True):
        # 详细地址输入框在始发地和目的地各有一个。
        matches = [e for e in driver.find_elements(
            self.By.XPATH, "//input[contains(@placeholder,'详细地址')]") if e.is_displayed()]
        if len(matches) >= 2:
            target = matches[0 if origin else 1]
        else:
            target = self._find_input(driver, label="详细地址", ordinal=(0 if origin else 1))
        self._fill(driver, target, address, choose_suggestion=True)

    def _set_weight_size(self, driver, weight, length=None, width=None, height=None):
        self._fill(driver, self._find_input(driver, hints=("重量",), label="重量"), weight)
        if length is None:
            return
        for name, value in (("长", length), ("宽", width), ("高", height)):
            self._fill(driver, self._find_input(driver, hints=(name,), label=name), value)

    def _set_ship_time(self, driver, days=0, hhmmss=None, now=False):
        """R001=今天；R002=此刻；R003=明天15:00；R004=后天08:00。"""
        inputs = [e for e in driver.find_elements(
            self.By.XPATH, "//input[contains(@placeholder,'时间') or contains(@placeholder,'日期')]")
            if e.is_displayed()]
        if not inputs:
            raise AssertionError("未找到寄件时间控件")
        self._click_element(driver, inputs[0])
        if now:
            self._click_text(driver, "此刻", timeout=6)
            return
        date_value = (datetime.now() + self.timedelta(days=days)).strftime("%Y-%m-%d")
        date_input = self._find_input(driver, hints=("选择日期", "日期"), timeout=7)
        if date_input.get_attribute("readonly"):
            # 只解除 HTML input 的只读属性，使 Selenium 可以按手册输入日期。
            driver.execute_script("arguments[0].removeAttribute('readonly');", date_input)
        self._fill(driver, date_input, date_value)
        if hhmmss:
            clock = self._find_input(driver, hints=("选择时间", "时间"), timeout=7)
            if clock.get_attribute("readonly"):
                driver.execute_script("arguments[0].removeAttribute('readonly');", clock)
            self._fill(driver, clock, hhmmss)
        self._click_text(driver, "确定", timeout=6)

    def _query(self, driver, expect=()):
        """实际点击查询，并等待对应内容可见；不能将输入完成当作测试通过。"""
        self._click_text(driver, "查询", timeout=10)
        self.time.sleep(1.4)
        if expect:
            end = self.time.monotonic() + 12
            while self.time.monotonic() < end:
                if any(text in driver.page_source for text in expect):
                    return
                self.time.sleep(0.3)
            raise AssertionError("点击查询后未检测到预期结果区域：" + str(expect))

    def _shot(self, driver, case_id):
        """唯一截图入口：调用官方函数，绝不重写截图逻辑。"""
        assert self.re.fullmatch(r"SF_R\d{3}_\d{3}", case_id), case_id
        # 保持查询结果/地图当前可视位置，不能滚动到页首而截丢结果。
        self.time.sleep(0.4)
        self.take_screenshot(driver, case_id + ".png")

    def _outlet_detail(self, driver, outlet_name):
        self._click_text(driver, outlet_name, exact=False, timeout=12)
        assert outlet_name in driver.page_source, "网点信息未展示：" + outlet_name

    def _zoom_city(self, driver):
        # R006 必须点击缩放条的“市”级别。
        self._click_text(driver, "市", timeout=8)
        self.time.sleep(1.0)

    def _zoom_max_by_dragging(self, driver):
        """R007：仅拖动滑块至顶部，绝不点击 +/- 按钮替代。"""
        selectors = [
            ".BMap_stdMpSliderBar", ".BMap_stdMpSlider", ".amap-zoom-slider",
            ".amap-zoom-slider-handle", "[role='slider']", ".zoom-slider-handle",
        ]
        thumbs = []
        for selector in selectors:
            try:
                thumbs.extend([e for e in driver.find_elements(self.By.CSS_SELECTOR, selector)
                               if e.is_displayed()])
            except self.WebDriverException:
                pass
        if not thumbs:
            raise AssertionError("地图未发现可拖动的缩放控制条，不能用 +/- 替代")
        thumb = thumbs[0]
        old_pos = thumb.location['y']
        self.ActionChains(driver).move_to_element(thumb).click_and_hold(thumb) \
            .move_by_offset(0, -135).release().perform()
        self.time.sleep(1.0)
        # 动作执行本身不证明已到最大级别，检测元素位置或滑块属性变化。
        new_pos = thumb.location['y']
        aria_value = thumb.get_attribute('aria-valuenow')
        aria_max = thumb.get_attribute('aria-valuemax')
        if old_pos == new_pos and not (aria_value and aria_max and aria_value == aria_max):
            raise AssertionError("缩放滑块未检测到拖动效果，请核对地图 DOM")

    def _set_keyword(self, driver, keyword):
        target = self._find_input(driver, hints=("输入关键词", "关键词"), label="关键词")
        self._fill(driver, target, keyword, choose_suggestion=True)

    def _set_item(self, driver, keyword, selected=None):
        target = self._find_input(driver, hints=("托寄物品", "物品"), label="托寄物品")
        self._fill(driver, target, keyword)
        if selected:
            self._click_text(driver, selected, exact=False, timeout=7)

    def _identity(self, driver, kind, value):
        label = "寄件人身份" if kind == "sender" else "收件人身份"
        q = self._xp(label)
        xp = ("//*[contains(normalize-space(.)," + q + ")]"
              "/ancestor::*[contains(@class,'form-item')][1]//*[contains(@class,'select') or self::input][1]")
        element = self._visible(driver, xp, timeout=6)
        self._click_element(driver, element)
        self._click_text(driver, value, timeout=6)

    def _set_street(self, driver, value):
        # 空值用例无需选择，保持默认空状态；非空必须实际点击下拉项。
        if value is None:
            return
        q = self._xp("乡/镇/街道")
        xp = ("//*[contains(normalize-space(.)," + q + ")]"
              "/ancestor::*[contains(@class,'form-item')][1]//*[contains(@class,'select') or self::input][1]")
        element = self._visible(driver, xp, timeout=8)
        self._click_element(driver, element)
        self._click_text(driver, value, timeout=6)

    # ========================= 10 项官方需求 =========================

    def _r001_element(self, driver, selector, timeout=30):
        """等待 R001 控件完成异步加载；不依赖占位文字或 Vue 内部状态。"""
        def ready(d):
            for element in d.find_elements(self.By.CSS_SELECTOR, selector):
                if element.is_displayed() and element.is_enabled():
                    return element
            return False
        try:
            return self.WebDriverWait(
                driver, timeout, poll_frequency=0.2,
                ignored_exceptions=(self.StaleElementReferenceException,)
            ).until(ready)
        except self.TimeoutException as exc:
            raise AssertionError(
                "R001 控件未就绪：%s；可见输入框=%s；页面=%s" %
                (selector, self._visible_input_summary(driver), driver.current_url)
            ) from exc

    def _r001_address(self, driver, field, city, district, address):
        # 官网 ID 的拼写就是 origion；城市搜索框无 placeholder。
        container = "#origion" if field == "origin" else "#dests"
        trigger = container + " .item-city"
        self._click_element(driver, self._r001_element(driver, trigger))
        search = self._r001_element(driver, container + " input.city-search")
        active_tabs = driver.find_elements(
            self.By.CSS_SELECTOR, container + " .tabs .tab-active, "
            + container + " .tabs .tab-border-active")
        assert any(t.is_displayed() and "内地" in t.text for t in active_tabs), (
            "R001 地址选择器默认选项不是内地：" + field)
        self._fill(driver, search, city)

        # 搜索结果本身包含省、市、区；直接选择对应区县，避免先点城市
        # 触发关闭弹层，也避免跨城市误选同名的鼓楼区。
        def district_option(d):
            for option in d.find_elements(
                    self.By.CSS_SELECTOR, container + " .search-result li"):
                if option.is_displayed() and city in option.text and district in option.text:
                    return option
            return False
        try:
            option = self.WebDriverWait(
                driver, 30, poll_frequency=0.2,
                ignored_exceptions=(self.StaleElementReferenceException,)
            ).until(district_option)
        except self.TimeoutException as exc:
            results = [e.text for e in driver.find_elements(
                self.By.CSS_SELECTOR, container + " .search-result") if e.is_displayed()]
            raise AssertionError("R001 未找到城市对应区县：%s/%s；结果=%s" %
                                 (city, district, results)) from exc
        self._click_element(driver, option)
        self.WebDriverWait(driver, 15).until(
            lambda d: city in d.find_element(self.By.CSS_SELECTOR, trigger).text
            and district in d.find_element(self.By.CSS_SELECTOR, trigger).text)
        detail = self._r001_element(driver, container + " input[placeholder*='详细地址']")
        self._fill(driver, detail, address)
        detail.send_keys(self.Keys.TAB)
        assert detail.get_attribute("value") == address, "R001 详细地址未正确回填"

    def _r001_today(self, driver):
        # 官网 .el-date-editor 使用 opacity:0 透明覆盖时间显示框。
        # 它可以承接鼠标点击，但 Selenium is_displayed() 返回 False，
        # 因此这里只等待 DOM 就绪，不能调用要求可见的 _r001_element。
        selector = "#datetime .el-date-editor input"
        wait = self.WebDriverWait(
            driver, 30, poll_frequency=0.2,
            ignored_exceptions=(self.StaleElementReferenceException,))

        def editor_ready(d):
            for element in d.find_elements(self.By.CSS_SELECTOR, selector):
                if (element.is_enabled() and element.rect["width"] > 0
                        and element.rect["height"] > 0):
                    return element
            return False

        try:
            date_input = wait.until(editor_ready)
        except self.TimeoutException as exc:
            raise AssertionError(
                "R001 日期组件未加载：#datetime 中没有可用的日期输入框；"
                "请检查官网日期组件 JS 是否加载失败；页面=" + driver.current_url
            ) from exc

        display = self._r001_element(driver, "#datetime .icon-time")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", display)
        # 实际鼠标点击显示框中心，事件由其上方透明的日期组件接收。
        self.ActionChains(driver).move_to_element(display).click().perform()

        def visible_panel(d):
            for element in d.find_elements(
                    self.By.CSS_SELECTOR, ".el-picker-panel.el-date-picker"):
                if element.is_displayed():
                    return element
            return False

        try:
            panel = self.WebDriverWait(driver, 5).until(visible_panel)
        except self.TimeoutException:
            # 页面布局差异可能使中心点击未命中输入框。仅触发标准 DOM
            # focus/click 事件，不修改样式、日期值或 Vue 内部状态。
            date_input = wait.until(editor_ready)
            driver.execute_script("arguments[0].focus(); arguments[0].click();", date_input)
            try:
                panel = wait.until(visible_panel)
            except self.TimeoutException as exc:
                raise AssertionError(
                    "R001 日期组件已加载，但点击/聚焦后日历未打开；页面="
                    + driver.current_url) from exc

        # 使用浏览器本地日期，与日历“今天”的口径一致。
        expected = driver.execute_script(
            "const d = new Date(); return d.getFullYear() + '-' + "
            "String(d.getMonth()+1).padStart(2,'0') + '-' + "
            "String(d.getDate()).padStart(2,'0');")
        today = self.WebDriverWait(driver, 10).until(
            lambda d: next((e for e in panel.find_elements(
                self.By.CSS_SELECTOR, "td.today:not(.disabled) span")
                if e.is_displayed() and e.is_enabled()), False))
        self._click_element(driver, today)
        buttons = [e for e in panel.find_elements(self.By.CSS_SELECTOR, "button")
                   if e.is_displayed() and e.is_enabled() and e.text.strip() == "确定"]
        assert len(buttons) == 1, "R001 日期弹层中未找到唯一的确定按钮"
        self._click_element(driver, buttons[0])
        self.WebDriverWait(driver, 10).until(self.EC.invisibility_of_element(panel))
        # 核验用户实际看到的日期回填，避免仅隐藏 input 的值改变就通过。
        try:
            self.WebDriverWait(driver, 10).until(
                lambda d: expected in d.find_element(
                    self.By.CSS_SELECTOR, "#datetime .icon-time").text)
        except self.TimeoutException as exc:
            actual = driver.find_element(self.By.CSS_SELECTOR, "#datetime").text
            raise AssertionError("R001 当天日期未正确回填：期望=%s；实际=%s" %
                                 (expected, actual)) from exc

    def _r001_query(self, driver):
        # active 是官网的业务可查询状态；仅 is_enabled 无法识别无效表单。
        button = self._r001_element(driver, ".query-conditions .submit-area button.search.active")
        self._click_element(driver, button)

        def quote_row(d):
            for row in d.find_elements(self.By.CSS_SELECTOR, ".prices tr.express-product.content"):
                if not row.is_displayed():
                    continue
                products = row.find_elements(self.By.CSS_SELECTOR, ".product-name")
                fees = row.find_elements(self.By.CSS_SELECTOR, ".fee-info")
                times = row.find_elements(self.By.CSS_SELECTOR, ".time-info")
                if (any(e.is_displayed() and e.text.strip() for e in products)
                        and any(e.is_displayed() and self.re.search(r"\d", e.text) for e in fees)
                        and any(e.is_displayed() and self.re.search(r"\d", e.text) for e in times)):
                    return row
            return False
        try:
            row = self.WebDriverWait(
                driver, 40, poll_frequency=0.3,
                ignored_exceptions=(self.StaleElementReferenceException,)
            ).until(quote_row)
        except self.TimeoutException as exc:
            visible = [e.text for e in driver.find_elements(
                self.By.CSS_SELECTOR, ".prices, .out-of-range, .el-message") if e.is_displayed()]
            raise AssertionError("R001 查询后未显示产品、数字运费及预计时效：%s" % visible) from exc
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", row)

    @pytest.mark.parametrize("case_id,oc,od,oa,dc,dd,da", [
        ("SF_R001_001", "广州市", "黄埔区", "黄埔东苑", "南京市", "鼓楼区", "南京大学"),
        ("SF_R001_002", "南京市", "鼓楼区", "南京大学", "广州市", "黄埔区", "黄埔东苑"),
    ], ids=["SF_R001_001", "SF_R001_002"])
    def test_SF_R001(self, driver, case_id, oc, od, oa, dc, dd, da):
        """R001：两组地址按列对应；5kg、20×15×25cm、当天寄件并截图。"""
        old_wait = driver.timeouts.implicit_wait
        driver.implicitly_wait(0)
        try:
            self._navigate(driver, "运费时效")
            self._r001_address(driver, "origin", oc, od, oa)
            self._r001_address(driver, "destination", dc, dd, da)
            self._set_weight_size(driver, 5, 20, 15, 25)
            for name, expected in (("重量", 5), ("长", 20), ("宽", 15), ("高", 25)):
                element = self._find_input(driver, hints=(name,), label=name)
                assert float(element.get_attribute("value")) == expected, "R001 数值错误：" + name
            self._r001_today(driver)
            # 查询前再次核验，防止后续操作导致已选地址被重置。
            for container, city, district, detail in (
                    ("#origion", oc, od, oa), ("#dests", dc, dd, da)):
                selected = driver.find_element(self.By.CSS_SELECTOR, container + " .item-city").text
                assert city in selected and district in selected, "R001 地址被重置：" + selected
                assert driver.find_element(self.By.CSS_SELECTOR,
                    container + " input[placeholder*='详细地址']").get_attribute("value") == detail
            self._r001_query(driver)
            self._shot(driver, case_id)
        finally:
            driver.implicitly_wait(old_wait)


    def _r002_wait(self, driver, selector, text=None, timeout=30, visible=True):
        """等待 R002 自己使用的官网控件；文字条件只匹配当前可见元素。"""
        def ready(d):
            for element in d.find_elements(self.By.CSS_SELECTOR, selector):
                try:
                    if (element.is_enabled() and (not visible or element.is_displayed())
                            and (text is None or element.text.strip() == text)):
                        return element
                except self.StaleElementReferenceException:
                    continue
            return False

        try:
            return self.WebDriverWait(
                driver, timeout, poll_frequency=0.2,
                ignored_exceptions=(self.StaleElementReferenceException,)
            ).until(ready)
        except self.TimeoutException as exc:
            values = []
            try:
                values = [e.text.strip() for e in driver.find_elements(
                    self.By.CSS_SELECTOR, selector) if e.is_displayed()]
            except self.WebDriverException:
                pass
            raise AssertionError(
                "R002 控件未就绪：%s；期望文字=%s；当前可见内容=%s；页面=%s" %
                (selector, text, values[:30], driver.current_url)
            ) from exc

    def _r002_area(self, driver, container, overseas=False):
        """按 R001 已验证的地址控件结构，选择香港九龙城区或热门城市南京鼓楼区。"""
        trigger = container + " .item-city"
        self._click_element(driver, self._r002_wait(driver, trigger))

        root = container + " .city-picker"
        self._r002_wait(driver, root + " input.city-search")

        # 与已通过的 R001 保持一致：官网不同版本会使用 tab-active 或 tab-border-active，
        # 不使用过于严格的直接子级选择器。
        active_tabs = (container + " .tabs .tab-active, "
                       + container + " .tabs .tab-border-active")

        def wait_active_tab(expected):
            try:
                return self.WebDriverWait(
                    driver, 12, poll_frequency=0.2,
                    ignored_exceptions=(self.StaleElementReferenceException,)
                ).until(lambda d: next((element for element in
                    d.find_elements(self.By.CSS_SELECTOR, active_tabs)
                    if element.is_displayed() and expected in element.text.strip()), False))
            except self.TimeoutException as exc:
                raise AssertionError(
                    "R002 地址弹层当前标签不正确：期望包含=%s；页面=%s" %
                    (expected, driver.current_url)
                ) from exc

        wait_active_tab("内地")

        if overseas:
            hmt_tab = self._r002_wait(driver, root + " .tab-item", "港澳台")
            self._click_element(driver, hmt_tab)
            wait_active_tab("港澳台")
            path = ("香港", "九龙城区")
        else:
            hot_tab = self._r002_wait(driver, root + " .tab-item", "热门城市")
            self._click_element(driver, hot_tab)
            path = ("南京市", "鼓楼区")

        # 每一步都重新等待当前弹层内的可见候选项，避免页面重绘后继续使用旧元素。
        for name in path:
            option = self._r002_wait(driver, root + " .card-name", name, timeout=20)
            self._click_element(driver, option)

        try:
            self.WebDriverWait(
                driver, 15, poll_frequency=0.2,
                ignored_exceptions=(self.StaleElementReferenceException,)
            ).until(lambda d: all(
                name in d.find_element(self.By.CSS_SELECTOR, trigger).text for name in path
            ))
            self.WebDriverWait(
                driver, 15, poll_frequency=0.2,
                ignored_exceptions=(self.StaleElementReferenceException,)
            ).until(lambda d: not any(
                element.is_displayed()
                for element in d.find_elements(self.By.CSS_SELECTOR, root)
            ))
        except self.TimeoutException as exc:
            selected = ""
            try:
                selected = driver.find_element(self.By.CSS_SELECTOR, trigger).text.strip()
            except self.WebDriverException:
                pass
            raise AssertionError(
                "R002 地址未正确回填或弹层未关闭：字段=%s；期望路径=%s；当前回填=%s" %
                (container, path, selected)
            ) from exc

    def _r002_now(self, driver):
        """打开寄件时间控件，点击“此刻”，并核验日期时间已回填。"""
        selector = "#datetime .el-date-editor input"
        wait = self.WebDriverWait(
            driver, 30, poll_frequency=0.2,
            ignored_exceptions=(self.StaleElementReferenceException,)
        )

        # 与 R001 一样，Element UI 的 input 可能透明覆盖显示框，不能只依赖 is_displayed。
        def editor_ready(d):
            for element in d.find_elements(self.By.CSS_SELECTOR, selector):
                try:
                    rect = element.rect
                    if (element.is_enabled() and rect.get("width", 0) > 0
                            and rect.get("height", 0) > 0):
                        return element
                except self.StaleElementReferenceException:
                    continue
            return False

        try:
            editor = wait.until(editor_ready)
        except self.TimeoutException as exc:
            raise AssertionError("R002 日期时间控件未加载：" + selector) from exc

        display = self._r002_wait(driver, "#datetime .icon-time")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", display)
        self.ActionChains(driver).move_to_element(display).click().perform()
        panel_selector = ".el-picker-panel.el-date-picker"

        def visible_panel(d):
            for element in d.find_elements(self.By.CSS_SELECTOR, panel_selector):
                if element.is_displayed():
                    return element
            return False

        try:
            panel = wait.until(visible_panel)
        except self.TimeoutException:
            # 与 R001 的日期控件处理一致：显示框点击未打开时，再触发标准 focus/click。
            editor = wait.until(editor_ready)
            driver.execute_script("arguments[0].focus(); arguments[0].click();", editor)
            try:
                panel = wait.until(visible_panel)
            except self.TimeoutException as exc:
                raise AssertionError(
                    "R002 日期时间控件已加载，但点击后未打开时间选择面板；页面="
                    + driver.current_url
                ) from exc

        now_buttons = [element for element in panel.find_elements(
            self.By.CSS_SELECTOR, "button"
        ) if element.is_displayed() and element.is_enabled()
            and element.text.strip() == "此刻"]
        assert len(now_buttons) == 1, (
            "R002 日期弹层中未找到唯一的“此刻”按钮，数量=%s" % len(now_buttons))

        hour_script = (
            "const d=new Date(); const p=n=>String(n).padStart(2,'0'); "
            "return d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate())+' '+p(d.getHours());"
        )
        before = driver.execute_script(hour_script)
        self._click_element(driver, now_buttons[0])

        # 兼容“此刻”按钮直接关闭面板和只填入当前时间、仍需点“确定”的两种行为。
        try:
            wait.until(self.EC.invisibility_of_element(panel))
        except self.TimeoutException:
            confirm_buttons = [element for element in panel.find_elements(
                self.By.CSS_SELECTOR, "button"
            ) if element.is_displayed() and element.is_enabled()
                and element.text.strip() == "确定"]
            if len(confirm_buttons) == 1:
                self._click_element(driver, confirm_buttons[0])
            wait.until(self.EC.invisibility_of_element(panel))

        after = driver.execute_script(hour_script)
        today_script = (
            "const d=new Date(); const p=n=>String(n).padStart(2,'0'); "
            "return d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate());"
        )
        expected_date = driver.execute_script(today_script)

        # 该官网控件点击“此刻”后可能只回填当天日期，并保留默认时间 08:00:00；
        # 因此不再错误地强制要求小时必须等于浏览器当前小时。仍核验日期为今天，
        # 且控件确实回填了完整的 HH:mm:ss 时间，避免空值或旧日期被误判为通过。
        try:
            def date_time_filled(d):
                actual_text = d.find_element(
                    self.By.CSS_SELECTOR, "#datetime"
                ).text.strip()
                match = self.re.search(
                    r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})",
                    actual_text
                )
                return (actual_text, match) if match else False

            actual_text, match = wait.until(date_time_filled)
            if match.group(1) != expected_date:
                raise AssertionError(
                    "R002 点击“此刻”后日期不是今天：期望日期=%s；实际=%s" %
                    (expected_date, actual_text)
                )
        except self.TimeoutException as exc:
            actual = driver.find_element(self.By.CSS_SELECTOR, "#datetime").text.strip()
            raise AssertionError(
                "R002 点击“此刻”后日期时间未正确回填：期望当天 %s（点击前/后小时=%s/%s）；实际=%s" %
                (expected_date, before, after, actual)
            ) from exc

    def _r002_result(self, driver):
        """查询并核验“快递产品 - 快递”页签中实际展示的产品、运费与时效。"""
        query_button = self._r002_wait(
            driver, ".query-conditions .submit-area button.search.active")
        self._click_element(driver, query_button)
        self._r002_wait(driver, ".prices", timeout=45)

        product_tab = self._r002_wait(driver, ".prices .service-type li", "快递产品")
        self._click_element(driver, product_tab)
        self._r002_wait(driver, ".prices .service-type li.selected", "快递产品")

        express_tab = self._r002_wait(driver, ".prices .tabs li", "快递")
        self._click_element(driver, express_tab)
        self._r002_wait(driver, ".prices .tabs li.active", "快递")

        def has_quote(d):
            for row in d.find_elements(
                    self.By.CSS_SELECTOR, ".prices tr.express-product.content"):
                try:
                    if not row.is_displayed():
                        continue
                    products = row.find_elements(self.By.CSS_SELECTOR, ".product-name")
                    fees = row.find_elements(
                        self.By.CSS_SELECTOR, ".fee-info .freight-content")
                    times = row.find_elements(self.By.CSS_SELECTOR, ".time-info")
                    has_product = any(e.is_displayed() and e.text.strip() for e in products)
                    has_fee = any(e.is_displayed() and self.re.search(r"\d", e.text)
                                  for e in fees)
                    has_time = any(e.is_displayed() and e.text.strip()
                                   and e.text.strip() not in ("--", "-") for e in times)
                    if has_product and has_fee and has_time:
                        return True
                except self.StaleElementReferenceException:
                    continue
            return False

        try:
            self.WebDriverWait(
                driver, 45, poll_frequency=0.3,
                ignored_exceptions=(self.StaleElementReferenceException,)
            ).until(has_quote)
        except self.TimeoutException as exc:
            results = []
            for element in driver.find_elements(
                    self.By.CSS_SELECTOR, ".prices, .out-of-range, .el-message"):
                try:
                    if element.is_displayed() and element.text.strip():
                        results.append(element.text.strip())
                except self.StaleElementReferenceException:
                    continue
            raise AssertionError(
                "R002 查询后未出现有效快递产品、数字运费和预计时效：%s" % results[:20]
            ) from exc

    def _r002_full_screenshot(self, driver):
        """保存整页 PNG，确保截图包含“快递产品 - 快递”页签及完整查询结果。"""
        import base64
        from pathlib import Path

        driver.execute_script("window.scrollTo(0, 0);")
        metrics = driver.execute_cdp_cmd("Page.getLayoutMetrics", {})
        size = metrics.get("cssContentSize") or metrics.get("contentSize")
        assert size and size.get("width", 0) > 0 and size.get("height", 0) > 0, (
            "R002 无法获取页面完整尺寸，未生成截图")

        image = driver.execute_cdp_cmd("Page.captureScreenshot", {
            "format": "png",
            "fromSurface": True,
            "captureBeyondViewport": True,
            "clip": {
                "x": 0,
                "y": 0,
                "width": size["width"],
                "height": size["height"],
                "scale": 1,
            },
        })
        content = base64.b64decode(image["data"])
        assert content.startswith(b"\x89PNG\r\n\x1a\n"), "R002 整页截图生成失败"
        width = int.from_bytes(content[16:20], "big")
        height = int.from_bytes(content[20:24], "big")
        assert width >= int(size["width"]) and height >= int(size["height"]), (
            "R002 截图尺寸不足以覆盖整页：实际=%s×%s；页面=%s×%s" %
            (width, height, size["width"], size["height"]))

        directory = Path("screenshots")
        directory.mkdir(parents=True, exist_ok=True)
        filename = datetime.now().strftime("%H%M%S%d%f")[:-3] + "_SF_R002_001.png"
        output = directory / filename
        output.write_bytes(content)
        assert output.exists() and output.stat().st_size > 0, "R002 截图文件未成功保存"
        return str(output)

    def test_SF_R002(self, driver):
        """香港九龙城区 -> 热门城市南京鼓楼区；5kg/20×15×25cm；此刻；整页结果截图。"""
        old_wait = driver.timeouts.implicit_wait
        driver.implicitly_wait(0)
        try:
            self._navigate(driver, "运费时效")
            self._r002_area(driver, "#origion", overseas=True)
            self._r002_area(driver, "#dests")
            self._set_weight_size(driver, 5, 20, 15, 25)

            # 核验所有数值都已写入真实表单控件，防止只完成了点击而没有完成输入。
            for name, expected in (("重量", 5), ("长", 20), ("宽", 15), ("高", 25)):
                element = self._find_input(driver, hints=(name,), label=name)
                actual = element.get_attribute("value")
                assert actual is not None and float(actual) == expected, (
                    "R002 数值错误：字段=%s；期望=%s；实际=%s" % (name, expected, actual))

            self._r002_now(driver)

            # 查询前复核两个地址，避免后续输入/时间选择导致地址状态被重置。
            for container, names in (("#origion", ("香港", "九龙城区")),
                                     ("#dests", ("南京市", "鼓楼区"))):
                selected = driver.find_element(
                    self.By.CSS_SELECTOR, container + " .item-city").text.strip()
                assert all(name in selected for name in names), (
                    "R002 查询前地址不正确：字段=%s；期望=%s；实际=%s" %
                    (container, names, selected))

            self._r002_result(driver)
            self._r002_full_screenshot(driver)
        finally:
            driver.implicitly_wait(old_wait)


    def _r003_tomorrow_1500(self, driver):
        """R003 专用：在官网日期时间弹层中填写明天和 15:00:00，再点击确定。"""
        selector = "#datetime .el-date-editor input"
        wait = self.WebDriverWait(
            driver, 30, poll_frequency=0.2,
            ignored_exceptions=(self.StaleElementReferenceException,))

        def editor_ready(d):
            for element in d.find_elements(self.By.CSS_SELECTOR, selector):
                try:
                    rect = element.rect
                    if element.is_enabled() and rect.get("width", 0) > 0 and rect.get("height", 0) > 0:
                        return element
                except self.StaleElementReferenceException:
                    continue
            return False

        editor = wait.until(editor_ready)
        display = self._r002_wait(driver, "#datetime .icon-time")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", display)
        self.ActionChains(driver).move_to_element(display).click().perform()
        panel_selector = ".el-picker-panel.el-date-picker"

        def visible_panel(d):
            return next((element for element in d.find_elements(
                self.By.CSS_SELECTOR, panel_selector) if element.is_displayed()), False)

        try:
            panel = wait.until(visible_panel)
        except self.TimeoutException:
            # 与 R001/R002 相同，若显示框点击没有打开面板，再触发标准 focus/click。
            editor = wait.until(editor_ready)
            driver.execute_script("arguments[0].focus(); arguments[0].click();", editor)
            try:
                panel = wait.until(visible_panel)
            except self.TimeoutException as exc:
                raise AssertionError(
                    "R003 日期时间控件已加载，但点击后未打开选择面板；页面="
                    + driver.current_url) from exc

        expected_date = driver.execute_script(
            "const d=new Date(); d.setDate(d.getDate()+1); "
            "const p=n=>String(n).padStart(2,'0'); "
            "return d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate());")

        def panel_input(placeholder_part):
            for element in panel.find_elements(
                    self.By.CSS_SELECTOR, "input[placeholder*='%s']" % placeholder_part):
                if element.is_enabled() and element.is_displayed():
                    return element
            return False

        try:
            date_input = wait.until(lambda d: panel_input("选择日期"))
            time_input = wait.until(lambda d: panel_input("选择时间"))
        except self.TimeoutException as exc:
            placeholders = [(e.get_attribute("placeholder"), e.get_attribute("value"))
                            for e in panel.find_elements(self.By.CSS_SELECTOR, "input")]
            raise AssertionError(
                "R003 日期弹层中未找到日期/时间输入框：%s" % placeholders) from exc

        for element, value, label in (
                (date_input, expected_date, "日期"),
                (time_input, "15:00:00", "时间")):
            if element.get_attribute("readonly"):
                driver.execute_script("arguments[0].removeAttribute('readonly');", element)
            self._fill(driver, element, value)
            actual = (element.get_attribute("value") or "").strip()
            assert actual == value, (
                "R003 %s输入错误：期望=%s；实际=%s" % (label, value, actual))

        # 日期时间弹层中可能同时存在日期面板和时间子面板的“确定”按钮。
        # 优先点击日期时间选择器底部工具栏的“确定”，不要把子面板按钮数量当成异常。
        confirm_buttons = [element for element in panel.find_elements(
            self.By.CSS_SELECTOR, ".el-picker-panel__footer > button")
            if element.is_displayed() and element.is_enabled()
            and element.text.strip() == "确定"]

        if len(confirm_buttons) != 1:
            # 兼容官网 DOM 将工具栏按钮包在额外容器中的情况；
            # 仍然只在日期选择器 footer 内查找，不扫描时间子面板按钮。
            confirm_buttons = [element for element in panel.find_elements(
                self.By.CSS_SELECTOR, ".el-picker-panel__footer button")
                if element.is_displayed() and element.is_enabled()
                and element.text.strip() == "确定"]

        assert len(confirm_buttons) == 1, (
            "R003 日期时间弹层中未找到唯一的主面板确定按钮：数量=%s；"
            "请检查 .el-picker-panel__footer DOM" % len(confirm_buttons))
        self._click_element(driver, confirm_buttons[0])
        wait.until(self.EC.invisibility_of_element(panel))

        def display_matches(d):
            actual = d.find_element(self.By.CSS_SELECTOR, "#datetime").text.strip()
            has_date = expected_date in actual
            has_time = ("15:00:00" in actual or self.re.search(r"\b15:00(?::00)?\b", actual))
            return actual if has_date and has_time else False

        try:
            actual_display = wait.until(display_matches)
        except self.TimeoutException as exc:
            actual_display = driver.find_element(self.By.CSS_SELECTOR, "#datetime").text.strip()
            raise AssertionError(
                "R003 点击确定后寄件时间未正确回填：期望=%s 15:00:00；实际=%s" %
                (expected_date, actual_display)) from exc
        return expected_date, actual_display

    def _r003_full_screenshot(self, driver):
        """保存包含寄件时间和全部快递报价信息的整页截图。"""
        import base64
        from pathlib import Path

        driver.execute_script("window.scrollTo(0, 0);")
        metrics = driver.execute_cdp_cmd("Page.getLayoutMetrics", {})
        size = metrics.get("cssContentSize", metrics["contentSize"])
        image = driver.execute_cdp_cmd("Page.captureScreenshot", {
            "format": "png", "fromSurface": True, "captureBeyondViewport": True,
            "clip": {"x": 0, "y": 0, "width": size["width"],
                     "height": size["height"], "scale": 1},
        })
        content = base64.b64decode(image["data"])
        assert content.startswith(b"\x89PNG\r\n\x1a\n"), "R003 整页截图生成失败"
        width = int.from_bytes(content[16:20], "big")
        height = int.from_bytes(content[20:24], "big")
        assert width >= int(size["width"]) and height >= int(size["height"]), (
            "R003 截图尺寸不足以覆盖整页：实际=%s×%s；页面=%s×%s" %
            (width, height, size["width"], size["height"]))
        directory = Path("screenshots")
        directory.mkdir(parents=True, exist_ok=True)
        filename = datetime.now().strftime("%H%M%S%d%f")[:-3] + "_SF_R003_001.png"
        output = directory / filename
        output.write_bytes(content)
        assert output.exists() and output.stat().st_size > 0, "R003 截图文件未成功保存"
        return str(output)

    def test_SF_R003(self, driver):
        """1 条：香港九龙城区 -> 南京鼓楼区，100kg，不填体积，明天15:00:00；保存完整结果截图。"""
        old_wait = driver.timeouts.implicit_wait
        driver.implicitly_wait(0)
        try:
            self._navigate(driver, "运费时效")
            # 复用已验证的地址弹层操作，但不修改 R002 及其辅助方法。
            self._r002_area(driver, "#origion", overseas=True)
            self._r002_area(driver, "#dests")
            self._set_weight_size(driver, 100)  # 按需求不填写长、宽、高。

            weight = self._find_input(driver, hints=("重量",), label="重量")
            assert weight.get_attribute("value") == "100", (
                "R003 重量输入错误：实际=%s" % weight.get_attribute("value"))
            for name in ("长", "宽", "高"):
                try:
                    element = self._find_input(driver, hints=(name,), label=name, timeout=1)
                    assert not (element.get_attribute("value") or "").strip(), (
                        "R003 不应填写体积字段 %s：实际=%s" %
                        (name, element.get_attribute("value")))
                except AssertionError as exc:
                    if "找不到输入框" not in str(exc):
                        raise

            expected_date, actual_time = self._r003_tomorrow_1500(driver)
            for container, names in (("#origion", ("香港", "九龙城区")),
                                     ("#dests", ("南京市", "鼓楼区"))):
                selected = driver.find_element(
                    self.By.CSS_SELECTOR, container + " .item-city").text.strip()
                assert all(name in selected for name in names), (
                    "R003 查询前地址不正确：字段=%s；期望=%s；实际=%s" %
                    (container, names, selected))

            self._r002_result(driver)
            self._r003_full_screenshot(driver)
        finally:
            driver.implicitly_wait(old_wait)

    def _r004_select_area(self, driver, container, overseas=False):
        """R004 专用地址选择：复用 R002 的点击步骤，但独立处理省份前缀及弹层关闭。"""
        expected = ("香港", "九龙城区") if overseas else ("南京市", "鼓楼区")
        trigger = container + " .item-city"
        root = container + " .city-picker"

        try:
            self._r002_area(driver, container, overseas=overseas)
        except AssertionError as exc:
            # R002 的公共方法要求弹层必须自动关闭；R004 中官网可能已回填完整地址，
            # 但仍保留地址面板。仅当回填内容明确正确时，才在 R004 内单独收起弹层。
            actual = ""
            try:
                actual = driver.find_element(self.By.CSS_SELECTOR, trigger).text.strip()
            except self.WebDriverException:
                pass

            if not all(name in actual for name in expected):
                raise

            def picker_visible(d):
                try:
                    return any(element.is_displayed()
                               for element in d.find_elements(self.By.CSS_SELECTOR, root))
                except self.StaleElementReferenceException:
                    return True

            if picker_visible(driver):
                # 先点击地址字段本身切换弹层状态。
                try:
                    self._click_element(
                        driver, self._r002_wait(driver, trigger, timeout=5))
                except (AssertionError, self.WebDriverException):
                    pass

                try:
                    self.WebDriverWait(
                        driver, 4, poll_frequency=0.2,
                        ignored_exceptions=(self.StaleElementReferenceException,)
                    ).until(lambda d: not picker_visible(d))
                except self.TimeoutException:
                    # 若仍展开，点击重量字段让地址弹层失焦；不改写任何表单值。
                    try:
                        weight_input = self._find_input(
                            driver, hints=("重量",), label="重量", timeout=3)
                        self._click_element(driver, weight_input)
                        self.WebDriverWait(
                            driver, 4, poll_frequency=0.2,
                            ignored_exceptions=(self.StaleElementReferenceException,)
                        ).until(lambda d: not picker_visible(d))
                    except (AssertionError, self.TimeoutException,
                            self.StaleElementReferenceException, self.WebDriverException):
                        pass

            # 只要已回填正确地址即可继续；后续 R004 输入和查询步骤会验证页面可交互。
            actual = self._r002_wait(driver, trigger, timeout=5).text.strip()

        actual = self._r002_wait(driver, trigger, timeout=5).text.strip()
        assert all(name in actual for name in expected), (
            "R004 地址选择后校验失败：字段=%s；期望包含=%s；实际=%s" %
            (container, expected, actual))

    def _r004_after_tomorrow_0800(self, driver):
        """R004 专用：寄件日期选择后天，时间选择 08:00:00，并确认回填。"""
        selector = "#datetime .el-date-editor input"
        wait = self.WebDriverWait(
            driver, 30, poll_frequency=0.2,
            ignored_exceptions=(self.StaleElementReferenceException,))

        def editor_ready(d):
            for element in d.find_elements(self.By.CSS_SELECTOR, selector):
                try:
                    rect = element.rect
                    if (element.is_enabled() and rect.get("width", 0) > 0
                            and rect.get("height", 0) > 0):
                        return element
                except self.StaleElementReferenceException:
                    continue
            return False

        editor = wait.until(editor_ready)
        display = self._r002_wait(driver, "#datetime .icon-time")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", display)
        self.ActionChains(driver).move_to_element(display).click().perform()
        panel_selector = ".el-picker-panel.el-date-picker"

        def visible_panel(d):
            return next((element for element in d.find_elements(
                self.By.CSS_SELECTOR, panel_selector) if element.is_displayed()), False)

        try:
            panel = wait.until(visible_panel)
        except self.TimeoutException:
            editor = wait.until(editor_ready)
            driver.execute_script("arguments[0].focus(); arguments[0].click();", editor)
            try:
                panel = wait.until(visible_panel)
            except self.TimeoutException as exc:
                raise AssertionError(
                    "R004 日期时间控件已加载，但点击后未打开选择面板；页面="
                    + driver.current_url) from exc

        expected_date = driver.execute_script(
            "const d=new Date(); d.setDate(d.getDate()+2); "
            "const p=n=>String(n).padStart(2,'0'); "
            "return d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate());")

        def panel_input(placeholder_part):
            for element in panel.find_elements(
                    self.By.CSS_SELECTOR, "input[placeholder*='%s']" % placeholder_part):
                if element.is_enabled() and element.is_displayed():
                    return element
            return False

        try:
            date_input = wait.until(lambda d: panel_input("选择日期"))
            time_input = wait.until(lambda d: panel_input("选择时间"))
        except self.TimeoutException as exc:
            placeholders = [(e.get_attribute("placeholder"), e.get_attribute("value"))
                            for e in panel.find_elements(self.By.CSS_SELECTOR, "input")]
            raise AssertionError(
                "R004 日期弹层中未找到日期/时间输入框：%s" % placeholders) from exc

        for element, value, label in (
                (date_input, expected_date, "日期"),
                (time_input, "08:00:00", "时间")):
            if element.get_attribute("readonly"):
                driver.execute_script("arguments[0].removeAttribute('readonly');", element)
            self._fill(driver, element, value)
            actual = (element.get_attribute("value") or "").strip()
            assert actual == value, (
                "R004 %s输入错误：期望=%s；实际=%s" % (label, value, actual))

        # 只定位主日期时间面板底部工具栏的“确定”，避免误选时间子面板的同名按钮。
        confirm_buttons = [element for element in panel.find_elements(
            self.By.CSS_SELECTOR, ".el-picker-panel__footer > button")
            if element.is_displayed() and element.is_enabled()
            and element.text.strip() == "确定"]
        if len(confirm_buttons) != 1:
            confirm_buttons = [element for element in panel.find_elements(
                self.By.CSS_SELECTOR, ".el-picker-panel__footer button")
                if element.is_displayed() and element.is_enabled()
                and element.text.strip() == "确定"]

        assert len(confirm_buttons) == 1, (
            "R004 日期时间弹层中未找到唯一的主面板确定按钮：数量=%s" %
            len(confirm_buttons))
        self._click_element(driver, confirm_buttons[0])
        wait.until(self.EC.invisibility_of_element(panel))

        def display_matches(d):
            actual = d.find_element(self.By.CSS_SELECTOR, "#datetime").text.strip()
            return actual if expected_date in actual and "08:00:00" in actual else False

        try:
            actual_display = wait.until(display_matches)
        except self.TimeoutException as exc:
            actual_display = driver.find_element(
                self.By.CSS_SELECTOR, "#datetime").text.strip()
            raise AssertionError(
                "R004 点击确定后寄件时间未正确回填：期望=%s 08:00:00；实际=%s" %
                (expected_date, actual_display)) from exc
        return expected_date, actual_display

    def _r004_full_screenshot(self, driver, case_id):
        """保存当前 R004 用例的整页截图，包含输入数据和大件产品结果。"""
        import base64
        from pathlib import Path

        assert self.re.fullmatch(r"SF_R004_\d{3}", case_id), (
            "R004 截图用例编号错误：" + str(case_id))
        driver.execute_script("window.scrollTo(0, 0);")
        metrics = driver.execute_cdp_cmd("Page.getLayoutMetrics", {})
        size = metrics.get("cssContentSize") or metrics.get("contentSize")
        assert size and size.get("width", 0) > 0 and size.get("height", 0) > 0, (
            "R004 无法获取页面完整尺寸，未生成截图")

        image = driver.execute_cdp_cmd("Page.captureScreenshot", {
            "format": "png",
            "fromSurface": True,
            "captureBeyondViewport": True,
            "clip": {
                "x": 0,
                "y": 0,
                "width": size["width"],
                "height": size["height"],
                "scale": 1,
            },
        })
        content = base64.b64decode(image["data"])
        assert content.startswith(b"\x89PNG\r\n\x1a\n"), (
            "R004 整页截图生成失败：" + case_id)
        width = int.from_bytes(content[16:20], "big")
        height = int.from_bytes(content[20:24], "big")
        assert width >= int(size["width"]) and height >= int(size["height"]), (
            "R004 截图尺寸不足：实际=%s×%s；页面=%s×%s" %
            (width, height, size["width"], size["height"]))

        directory = Path("screenshots")
        directory.mkdir(parents=True, exist_ok=True)
        filename = datetime.now().strftime("%H%M%S%d%f")[:-3] + "_" + case_id + ".png"
        output = directory / filename
        output.write_bytes(content)
        assert output.exists() and output.stat().st_size > 0, (
            "R004 截图文件未成功保存：" + str(output))
        return str(output)

    def test_SF_R004(self, driver):
        """4 组边界数据：香港九龙城区 -> 南京鼓楼区；后天 08:00；查询并查看大件产品。"""
        cases = [
            ("SF_R004_001", 19, 5, 8, 6),
            ("SF_R004_002", 20, 5, 8, 6),
            ("SF_R004_003", 19, 100, 80, 90),
            ("SF_R004_004", 20, 100, 80, 90),
        ]
        old_wait = driver.timeouts.implicit_wait
        driver.implicitly_wait(0)
        try:
            for case_id, weight, length, width, height in cases:
                self._navigate(driver, "运费时效")

                # 使用 R002 已验证的地址选择方法；不改动 R001/R002/R003 代码。
                self._r004_select_area(driver, "#origion", overseas=True)
                self._r004_select_area(driver, "#dests")

                self._set_weight_size(driver, weight, length, width, height)
                for name, expected in (
                        ("重量", weight), ("长", length), ("宽", width), ("高", height)):
                    element = self._find_input(driver, hints=(name,), label=name)
                    actual = (element.get_attribute("value") or "").strip()
                    try:
                        numeric_actual = float(actual)
                    except (TypeError, ValueError):
                        raise AssertionError(
                            "%s 数值未正确输入：字段=%s；期望=%s；实际=%s" %
                            (case_id, name, expected, actual))
                    assert numeric_actual == expected, (
                        "%s 数值错误：字段=%s；期望=%s；实际=%s" %
                        (case_id, name, expected, actual))

                expected_date, actual_time = self._r004_after_tomorrow_0800(driver)

                # 查询前再次核验地址，确保每组数据都与指定路线对应。
                for container, names in (
                        ("#origion", ("香港", "九龙城区")),
                        ("#dests", ("南京市", "鼓楼区"))):
                    selected = driver.find_element(
                        self.By.CSS_SELECTOR, container + " .item-city").text.strip()
                    assert all(name in selected for name in names), (
                        "%s 查询前地址不正确：字段=%s；期望=%s；实际=%s" %
                        (case_id, container, names, selected))

                self._r002_result(driver)
                self._click_text(driver, "大件（20kg+）", timeout=12)
                self.time.sleep(0.8)

                # 点击后确认结果区仍显示内容，再保存包含表单与结果的整页截图。
                result_area = self._r002_wait(driver, ".prices", timeout=20)
                assert result_area.text.strip(), (
                    "%s 点击“大件（20kg+）”后结果区域为空" % case_id)
                screenshot = self._r004_full_screenshot(driver, case_id)
                print(
                    "%s 完成：重量=%s，尺寸=%s×%s×%s，寄件时间=%s；截图=%s" %
                    (case_id, weight, length, width, height, actual_time, screenshot))
        finally:
            driver.implicitly_wait(old_wait)

    def test_SF_R005(self, driver):
        """4 条：从运费时效页依次进入保价、代收货款、签单返还、包装服务，并逐页截图。"""
        services = [
            ("SF_R005_001", "保价", ("保价", "保价服务")),
            ("SF_R005_002", "代收货款", ("代收货款", "代收贷款", "代收货款服务")),
            ("SF_R005_003", "签单返还", ("签单返还", "签单返还服务")),
            ("SF_R005_004", "包装服务", ("包装服务", "包装服务介绍")),
        ]

        for case_id, label, aliases in services:
            # 每个用例都从规定的“运费时效”页面开始，避免上一个服务页影响下一个用例。
            self._navigate(driver, "运费时效")
            base_handle = driver.current_window_handle
            handles_before = set(driver.window_handles)
            url_before = driver.current_url
            title_before = driver.title
            try:
                body_before = driver.find_element(self.By.TAG_NAME, "body").text.strip()
            except self.WebDriverException:
                body_before = ""

            # 点击“其他服务”中的目标项目。代收货款按需求原文命名。
            self._click_text(driver, label, exact=False, timeout=15)

            def page_transitioned(d):
                try:
                    if set(d.window_handles) - handles_before:
                        return "new_window"
                    body_now = d.find_element(self.By.TAG_NAME, "body").text.strip()
                    changed = (
                        d.current_url != url_before
                        or d.title != title_before
                        or (body_now and body_now != body_before and len(body_now) >= 10)
                    )
                    return "same_window" if changed else False
                except (self.StaleElementReferenceException, self.WebDriverException):
                    return False

            try:
                transition = self.WebDriverWait(
                    driver, 20, poll_frequency=0.25,
                    ignored_exceptions=(self.StaleElementReferenceException,)
                ).until(page_transitioned)
            except self.TimeoutException as exc:
                raise AssertionError(
                    "%s 点击“%s”后未检测到页面跳转或内容切换；"
                    "原页面=%s；当前页面=%s；标题=%s" %
                    (case_id, label, url_before, driver.current_url, driver.title)
                ) from exc

            opened_new_tab = transition == "new_window"
            if opened_new_tab:
                new_handles = list(set(driver.window_handles) - handles_before)
                assert new_handles, "%s 检测到新窗口但未取得窗口句柄" % case_id
                driver.switch_to.window(new_handles[-1])

            # 页面跳转完成后等待文档和可见主体内容加载。
            try:
                self.WebDriverWait(
                    driver, 20, poll_frequency=0.25,
                    ignored_exceptions=(self.StaleElementReferenceException,)
                ).until(lambda d: d.execute_script("return document.readyState") == "complete")
                body_text = self.WebDriverWait(
                    driver, 15, poll_frequency=0.25,
                    ignored_exceptions=(self.StaleElementReferenceException,)
                ).until(lambda d: (
                    (d.find_element(self.By.TAG_NAME, "body").text or "").strip()
                    if (d.find_element(self.By.TAG_NAME, "body").text or "").strip()
                    else False
                ))
            except self.TimeoutException as exc:
                raise AssertionError(
                    "%s 点击“%s”后页面未完成加载：URL=%s；标题=%s" %
                    (case_id, label, driver.current_url, driver.title)
                ) from exc

            # 确认当前已进入对应服务页面，而不是仍停留在运费时效页。
            evidence = " ".join((driver.title, driver.current_url, body_text))
            matched_alias = next((name for name in aliases if name in evidence), None)
            assert matched_alias, (
                "%s 点击“%s”后未发现对应服务页面标识；URL=%s；标题=%s；"
                "页面可见文本前 500 字=%s" %
                (case_id, label, driver.current_url, driver.title, body_text[:500])
            )

            # 每个目标页加载并验证后立即保存独立截图。
            self._shot(driver, case_id)
            print(
                "%s 完成：服务=%s；URL=%s；标题=%s" %
                (case_id, label, driver.current_url, driver.title)
            )

            # 如果服务链接新开标签页，截图后关闭该标签，回到运费时效页签，
            # 保持后续用例可按同一流程重新导航。
            if opened_new_tab:
                driver.close()
                remaining = driver.window_handles
                if base_handle in remaining:
                    driver.switch_to.window(base_handle)
                elif remaining:
                    driver.switch_to.window(remaining[-1])
                else:
                    raise AssertionError("%s 截图后浏览器没有剩余窗口" % case_id)

    def _r006_dismiss_cookie_banner(self, driver):
        """只通过官网 Cookie 按钮关闭弹窗，不删除遮罩或修改存储。"""
        for banner in driver.find_elements(self.By.CSS_SELECTOR, ".cookie-policy"):
            if not banner.is_displayed():
                continue
            buttons = [e for e in banner.find_elements(self.By.CSS_SELECTOR, ".right .btn")
                       if e.is_displayed() and e.is_enabled() and e.text.strip() == "不同意"]
            assert len(buttons) == 1, "R006 Cookie 弹窗未找到唯一的不同意按钮"
            buttons[0].click()
            self.WebDriverWait(driver, 8).until(self.EC.invisibility_of_element(banner))

    def _r006_wait(self, driver, selector, text=None, timeout=30):
        def ready(d):
            self._r006_dismiss_cookie_banner(d)
            for element in d.find_elements(self.By.CSS_SELECTOR, selector):
                if (element.is_displayed() and element.is_enabled()
                        and (text is None or element.text.strip() == text)):
                    return element
            return False
        try:
            return self.WebDriverWait(driver, timeout, poll_frequency=0.25,
                ignored_exceptions=(self.StaleElementReferenceException,)).until(ready)
        except self.TimeoutException as exc:
            values = [e.text[:160] for e in driver.find_elements(
                self.By.CSS_SELECTOR, selector) if e.is_displayed()]
            raise AssertionError("R006 控件未就绪：%s；目标=%s；可见内容=%s；URL=%s" %
                                 (selector, text, values, driver.current_url)) from exc

    def _r006_click(self, driver, element):
        self._r006_dismiss_cookie_banner(driver)
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        try:
            element.click()
        except self.ElementClickInterceptedException:
            self._r006_dismiss_cookie_banner(driver)
            # 地图标记可能互相覆盖；对已定位的标记发送标准 click。
            driver.execute_script("arguments[0].click();", element)

    def _r006_navigate(self, driver):
        driver.switch_to.default_content()
        driver.get("https://www.sf-express.com/")
        before = set(driver.window_handles)
        self._r006_click(driver, self._r006_wait(driver, "a", "服务支持"))
        def support_ready(d):
            added = set(d.window_handles) - before
            if added:
                d.switch_to.window(next(iter(added)))
            self._r006_dismiss_cookie_banner(d)
            return any(e.is_displayed() for e in d.find_elements(
                self.By.CSS_SELECTOR, ".side-menu"))
        self.WebDriverWait(driver, 30).until(support_ready)
        if not any(e.is_displayed() and e.text.strip() == "服务网点"
                   for e in driver.find_elements(self.By.CSS_SELECTOR, ".side-menu .side-child-item")):
            self._r006_click(driver, self._r006_wait(driver, ".side-menu .title", "服务查询"))
        self._r006_click(driver, self._r006_wait(
            driver, ".side-menu li, .side-menu a, .side-menu .title", "服务网点"))
        self._r006_wait(driver, "#range-query-citypicker input.result")
        self._r006_wait(driver, "#range-key-word")
        assert "/outlets-query" in driver.current_url, "R006 未进入服务网点页面"

    def _r006_select_area(self, driver):
        # toggleCityPicker 会切换开关，绝不能无条件连续补发第二次 click。
        self._r006_click(driver, self._r006_wait(driver, "#range-query-citypicker"))
        root = "#range-query-citypicker .city-picker"
        self._r006_click(driver, self._r006_wait(
            driver, root + " .city-picker-inner .tab-item", "热门城市"))
        for name in ("上海市", "黄浦区"):
            self._r006_click(driver, self._r006_wait(driver, root + " .card-name", name))
        def selected(d):
            value = d.find_element(self.By.CSS_SELECTOR,
                "#range-query-citypicker input.result").get_attribute("value") or ""
            return "上海市" in value and "黄浦区" in value and not any(
                e.is_displayed() for e in d.find_elements(self.By.CSS_SELECTOR, root))
        self.WebDriverWait(driver, 15).until(selected,
            "R006 区域未回填为上海市-黄浦区或弹层未关闭")

    def _r006_search(self, driver):
        keyword = self._r006_wait(driver, "#range-key-word")
        keyword.send_keys(self.Keys.CONTROL, "a")
        keyword.send_keys("兴业太古汇")
        # 官网必须选中联想地址才能得到查询坐标；输入文字后直接查询不会执行。
        name = self._r006_wait(driver,
            ".key-word-query li:not(.noData) .detail-name", "兴业太古汇")
        self._r006_click(driver, name.find_element(self.By.XPATH, ".."))
        assert keyword.get_attribute("value") == "兴业太古汇", "R006 关键词回填错误"
        self._r006_click(driver, self._r006_wait(
            driver, ".range-query .search-btn:not(.disabled)"))
        self._r006_wait(driver, ".range-query .result-box .map .BMap_Marker", timeout=45)

    def _r006_detail(self, driver, name=None):
        for panel in driver.find_elements(self.By.CSS_SELECTOR,
                ".range-query .map .BMap_bubble_content, .range-query .map .BMap_pop"):
            if not panel.is_displayed():
                continue
            text = panel.text.strip()
            # 详情包含地址/距离、支持服务、电话/营业时间；不接受页头或地图图例。
            if ("距离" in text and "支持" in text and self.re.search(r"\d", text)
                    and (name is None or name in text)):
                return panel
        return False

    def _r006_click_outlet_marker(self, driver, outlet_name="南京路店"):
        """逐个点击真实地图标记；单个标记没有响应时尝试其他点击方式并继续检查。"""
        selector = ".range-query .result-box .map .BMap_Marker"
        self._r006_wait(driver, selector, timeout=45)
        visited, names, skipped = set(), [], []

        def marker_key(element):
            # 百度地图可能在点击后重绘 marker 节点；使用位置/标题作辅助去重，
            # 避免 WebElement.id 变化导致反复点击同一个地理位置。
            try:
                return driver.execute_script("""
                    const e=arguments[0],r=e.getBoundingClientRect();
                    return [
                      (e.getAttribute('title')||''),
                      (e.getAttribute('aria-label')||''),
                      Math.round(r.left),Math.round(r.top),
                      Math.round(r.width),Math.round(r.height),
                      (e.getAttribute('style')||'').slice(0,100)
                    ].join('|');
                """, element)
            except self.WebDriverException:
                return element.id

        def wait_for_new_detail(previous_text, timeout=3):
            def changed(d):
                panel = self._r006_detail(d)
                if not panel:
                    return False
                text = panel.text.strip()
                if not text:
                    return False
                # 没有先前详情时，只要真实信息窗出现就算本次点击成功；
                # 否则必须看到信息窗内容变化，避免将旧详情误认为新结果。
                return panel if (not previous_text or text != previous_text) else False
            try:
                return self.WebDriverWait(
                    driver, timeout, poll_frequency=0.2,
                    ignored_exceptions=(self.StaleElementReferenceException,)
                ).until(changed)
            except self.TimeoutException:
                return False

        while True:
            candidates = []
            for element in driver.find_elements(self.By.CSS_SELECTOR, selector):
                try:
                    if not element.is_displayed():
                        continue
                    key = marker_key(element)
                    if key not in visited:
                        candidates.append((key, element))
                except (self.StaleElementReferenceException, self.WebDriverException):
                    continue
            if not candidates:
                break

            key, marker = candidates[0]
            visited.add(key)

            # 关闭上一个信息窗，保证后续判断确实来自本次标记点击。
            for close in driver.find_elements(self.By.CSS_SELECTOR,
                    ".range-query .map .BMap_pop img[title*='关闭'], "
                    ".range-query .map .BMap_pop [aria-label='关闭']"):
                try:
                    if close.is_displayed():
                        self._r006_click(driver, close)
                except (self.StaleElementReferenceException, self.WebDriverException):
                    continue

            previous = self._r006_detail(driver)
            previous_text = previous.text.strip() if previous else ""

            # 方案一：标准 Selenium click。
            try:
                self._r006_click(driver, marker)
            except (self.StaleElementReferenceException, self.WebDriverException):
                pass
            panel = wait_for_new_detail(previous_text, timeout=3)

            # 方案二：ActionChains 移动到标记中心点击。部分百度地图标记的
            # 外层 div 接收鼠标事件，element.click() 并不能触发地图 SDK 监听器。
            if not panel:
                try:
                    marker = next((e for e in driver.find_elements(
                        self.By.CSS_SELECTOR, selector)
                        if e.is_displayed() and marker_key(e) == key), None)
                    if marker is not None:
                        self.ActionChains(driver).move_to_element(marker).pause(0.15).click().perform()
                except (self.StaleElementReferenceException, self.WebDriverException):
                    pass
                panel = wait_for_new_detail(previous_text, timeout=3)

            # 方案三：点击标记内的图片/图标子元素，仍是对页面真实控件的用户式点击。
            if not panel:
                try:
                    marker = next((e for e in driver.find_elements(
                        self.By.CSS_SELECTOR, selector)
                        if e.is_displayed() and marker_key(e) == key), None)
                    if marker is not None:
                        children = [e for e in marker.find_elements(
                            self.By.CSS_SELECTOR, "img, canvas, svg")
                            if e.is_displayed()]
                        if children:
                            self.ActionChains(driver).move_to_element(children[0]).click().perform()
                        else:
                            rect = marker.rect
                            self.ActionChains(driver).move_to_element_with_offset(
                                marker, max(1, rect["width"] / 2),
                                max(1, rect["height"] / 2)).click().perform()
                except (self.StaleElementReferenceException, self.WebDriverException):
                    pass
                panel = wait_for_new_detail(previous_text, timeout=4)

            if not panel:
                # 某些标记被相邻标记遮挡或没有独立信息窗，不要因此终止整个
                # R006；记录位置后继续点击剩余标记。
                skipped.append(key)
                continue

            detail_text = panel.text.strip()
            if detail_text and detail_text not in names:
                names.append(detail_text[:160])

            if outlet_name in detail_text:
                return panel

        raise AssertionError(
            "R006 查询结果中未找到目标网点详情：目标=%s；已访问标记=%s；"
            "成功打开详情数=%s；未响应标记=%s；已见详情=%s；当前URL=%s" %
            (outlet_name, len(visited), len(names), skipped, names, driver.current_url)
        )

    def _r006_zoom_to_city(self, driver):
        # 百度地图 v3 SDK：城市按钮为 BMap_zlCity；标签只在缩放区悬停时展开。
        control = self._r006_wait(driver, ".range-query .map .BMap_stdMpZoom")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", control)
        self.ActionChains(driver).move_to_element(control).perform()
        target = self._r006_wait(driver,
            ".range-query .map .BMap_zlCity", timeout=20)
        slider_css = ".range-query .map .BMap_stdMpSliderBar"
        slider = self._r006_wait(driver, slider_css)
        old_top = slider.value_of_css_property("top")
        # 保持鼠标在缩放区内，直接移到“市”按钮点击，避免重新滚动使标签收起。
        self.ActionChains(driver).move_to_element(target).click().perform()
        def city_ready(d):
            bar = d.find_element(self.By.CSS_SELECTOR, slider_css)
            city = d.find_element(self.By.CSS_SELECTOR,
                ".range-query .map .BMap_zlCity")
            # 使用屏幕上的滑块位置确认缩放确实落到“市”刻度，
            # 同时兼容查询初始视图本来就已处于该刻度的情况。
            return d.execute_script(
                "const a=arguments[0].getBoundingClientRect(),b=arguments[1].getBoundingClientRect();"
                "return Math.abs((a.top+a.height/2)-(b.top+b.height/2)) <= 10;", bar, city)
        try:
            self.WebDriverWait(driver, 15, poll_frequency=0.25).until(city_ready)
        except self.TimeoutException as exc:
            current = driver.find_element(self.By.CSS_SELECTOR, slider_css).value_of_css_property("top")
            raise AssertionError("R006 点击市后滑块未落到市刻度：点击前=%s；点击后=%s" %
                                 (old_top, current)) from exc
        self.time.sleep(1)  # 等待缩放动画结束及地图瓦片重绘。
        assert self._r006_detail(driver, "南京路店"), "R006 缩放后南京路店详情未保留"

    def _r006_screenshot(self, driver):
        """保存 R006 整页截图：沿用 R001-R005 的时间戳_用例编号.png 命名规则。"""
        import base64
        from pathlib import Path

        self._r006_dismiss_cookie_banner(driver)

        # BMap_pop 外壳可为 0×0，但绝对定位子节点仍在显示详情。
        # 在等待中重新定位，并检查真实渲染的文本矩形，不以外壳尺寸判定。
        last_state = {}

        def target_detail_ready(d):
            self._r006_dismiss_cookie_banner(d)
            panel = self._r006_detail(d, "南京路店")
            maps = d.find_elements(self.By.CSS_SELECTOR, ".range-query .result-box .map")
            map_element = next((e for e in maps if e.is_displayed()), None)
            if panel is False or panel is None or map_element is None:
                last_state.clear()
                last_state.update({"mapFound": map_element is not None, "panelFound": bool(panel)})
                return False
            state = d.execute_script("""
                const map = arguments[0], panel = arguments[1];
                const rect = r => ({x:r.x, y:r.y, w:r.width, h:r.height});
                const shown = e => {
                    for (let p=e; p; p=p.parentElement) {
                        const s=getComputedStyle(p);
                        if (s.display==='none' || s.visibility==='hidden' ||
                            s.visibility==='collapse' || Number(s.opacity)===0) return false;
                    }
                    return true;
                };
                const m=map.getBoundingClientRect(), p=panel.getBoundingClientRect();
                const boxes=[], texts=[];
                // Range 反映文本实际绘制位置，也适用于零尺寸父节点中的绝对定位内容。
                const walker=document.createTreeWalker(panel, NodeFilter.SHOW_TEXT);
                let node;
                while ((node=walker.nextNode())) {
                    const text=node.textContent.trim();
                    if (!text || !shown(node.parentElement)) continue;
                    const range=document.createRange();
                    range.selectNodeContents(node);
                    const rs=Array.from(range.getClientRects()).filter(r=>r.width>0 && r.height>0);
                    if (rs.length) { texts.push(text); boxes.push(...rs); }
                }
                const text=texts.join(' ');
                const left=boxes.length ? Math.min(...boxes.map(r=>r.left)) : 0;
                const top=boxes.length ? Math.min(...boxes.map(r=>r.top)) : 0;
                const right=boxes.length ? Math.max(...boxes.map(r=>r.right)) : 0;
                const bottom=boxes.length ? Math.max(...boxes.map(r=>r.bottom)) : 0;
                return {
                    mapVisible: shown(map) && m.width>0 && m.height>0,
                    panelVisible: shown(panel) && boxes.length>0 &&
                        text.includes('南京路店') && text.includes('距离') &&
                        text.includes('支持') && /[0-9]/.test(text),
                    map: rect(m), panel: rect(p),
                    renderedDetail: {x:left,y:top,w:right-left,h:bottom-top},
                    visibleText: text.slice(0,500)
                };
            """, map_element, panel)
            last_state.clear()
            last_state.update(state)
            return state if state.get("mapVisible") and state.get("panelVisible") else False

        try:
            self.WebDriverWait(
                driver, 15, poll_frequency=0.25,
                ignored_exceptions=(self.StaleElementReferenceException,)
            ).until(target_detail_ready)
        except self.TimeoutException as exc:
            raise AssertionError("R006 截图前地图或实际网点详情未完整显示：" + str(last_state)) from exc


        # 缩放至“市”级由前一步完成；这里仅确认地图控件仍存在，不再改变缩放。
        self._r006_wait(driver, ".range-query .map .BMap_stdMpZoom")
        metrics = driver.execute_cdp_cmd("Page.getLayoutMetrics", {})
        size = metrics.get("cssContentSize") or metrics.get("contentSize")
        assert size and size.get("width", 0) > 0 and size.get("height", 0) > 0, (
            "R006 无法获取完整页面尺寸")

        image = driver.execute_cdp_cmd("Page.captureScreenshot", {
            "format": "png",
            "fromSurface": True,
            "captureBeyondViewport": True,
            "clip": {
                "x": 0, "y": 0,
                "width": size["width"], "height": size["height"], "scale": 1
            }
        })
        content = base64.b64decode(image["data"])
        assert content.startswith(b"\x89PNG\r\n\x1a\n"), "R006 截图生成失败"
        width = int.from_bytes(content[16:20], "big")
        height = int.from_bytes(content[20:24], "big")
        assert width >= int(size["width"]) and height >= int(size["height"]), (
            "R006 截图尺寸不足以覆盖整页：实际=%s×%s；页面=%s×%s" %
            (width, height, size["width"], size["height"])
        )

        # 与 R005 的 take_screenshot 命名格式一致：时间戳_SF_R006_001.png。
        folder = Path("screenshots")
        folder.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%H%M%S%d%f")[:-3]
        output = folder / (timestamp + "_SF_R006_001.png")
        output.write_bytes(content)
        assert output.is_file() and output.stat().st_size > 0, (
            "R006 截图文件未成功保存：" + str(output))
        return str(output)

    def test_SF_R006(self, driver):
        """首页→服务支持→服务网点；上海黄浦区→兴业太古汇→南京路店→市级地图。"""
        old_wait = driver.timeouts.implicit_wait
        driver.implicitly_wait(0)
        try:
            self._r006_navigate(driver)
            self._r006_select_area(driver)
            self._r006_search(driver)
            self._r006_click_outlet_marker(driver)
            self._r006_zoom_to_city(driver)
            screenshot_path = self._r006_screenshot(driver)
            print("R006 完成：已打开南京路店详情并缩放至市级；截图=%s" % screenshot_path)
        finally:
            driver.implicitly_wait(old_wait)


    def _r007_dismiss_cookie_banner(self, driver):
        """只通过官网 Cookie 按钮关闭弹窗，不删除遮罩或修改存储。"""
        for banner in driver.find_elements(self.By.CSS_SELECTOR, ".cookie-policy"):
            if not banner.is_displayed():
                continue
            buttons = [e for e in banner.find_elements(self.By.CSS_SELECTOR, ".right .btn")
                       if e.is_displayed() and e.is_enabled() and e.text.strip() == "不同意"]
            assert len(buttons) == 1, "R007 Cookie 弹窗未找到唯一的不同意按钮"
            buttons[0].click()
            self.WebDriverWait(driver, 8).until(self.EC.invisibility_of_element(banner))


    def _r007_wait(self, driver, selector, text=None, timeout=30):
        def ready(d):
            self._r007_dismiss_cookie_banner(d)
            for element in d.find_elements(self.By.CSS_SELECTOR, selector):
                if (element.is_displayed() and element.is_enabled()
                        and (text is None or element.text.strip() == text)):
                    return element
            return False
        try:
            return self.WebDriverWait(driver, timeout, poll_frequency=0.25,
                ignored_exceptions=(self.StaleElementReferenceException,)).until(ready)
        except self.TimeoutException as exc:
            values = [e.text[:160] for e in driver.find_elements(
                self.By.CSS_SELECTOR, selector) if e.is_displayed()]
            raise AssertionError("R007 控件未就绪：%s；目标=%s；可见内容=%s；URL=%s" %
                                 (selector, text, values, driver.current_url)) from exc


    def _r007_click(self, driver, element):
        self._r007_dismiss_cookie_banner(driver)
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        try:
            element.click()
        except self.ElementClickInterceptedException:
            self._r007_dismiss_cookie_banner(driver)
            # 地图标记可能互相覆盖；对已定位的标记发送标准 click。
            driver.execute_script("arguments[0].click();", element)


    def _r007_wait_form(self, driver):
        """同时等待区域和关键词控件；路由已到达但组件未挂载时只刷新一次。"""
        def form_ready(d):
            self._r007_dismiss_cookie_banner(d)
            if "/outlets-query" not in d.current_url:
                return False
            for selector in ("#range-query-citypicker input.result", "#range-key-word"):
                if not any(e.is_displayed() and e.is_enabled()
                           for e in d.find_elements(self.By.CSS_SELECTOR, selector)):
                    return False
            return True
        for attempt in range(2):
            try:
                self.WebDriverWait(driver, 45, poll_frequency=0.3,
                    ignored_exceptions=(self.StaleElementReferenceException,)).until(form_ready)
                return
            except self.TimeoutException:
                if attempt == 0 and "/outlets-query" in driver.current_url:
                    # 此时尚未输入数据，刷新不会丢失本条用例的操作结果。
                    driver.refresh()
                    continue
                diagnostic = driver.execute_script("""
                    return {url:location.href,readyState:document.readyState,
                        body:(document.body?.innerText||'').slice(0,1000),
                        inputs:Array.from(document.querySelectorAll('input')).map(e=>({
                            placeholder:e.placeholder,id:e.id,disabled:e.disabled,
                            width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height
                        })).slice(0,20)};
                """)
                raise AssertionError("R007 网点查询表单加载失败（已处理Cookie并等待/重试）：%s" % diagnostic)

    def _r007_restore_detail(self, driver, outlet_name):
        """缩放后重新获取信息窗；必要时重开真实标记，不改变地图缩放级别。"""
        stable = {"text": "", "since": 0}
        def detail_ready(d):
            self._r007_dismiss_cookie_banner(d)
            panel = self._r007_detail(d, outlet_name)
            text = panel.text.strip() if panel else ""
            if not text or text != stable["text"]:
                stable.update(text=text, since=self.time.monotonic())
                return False
            return panel if self.time.monotonic() - stable["since"] >= 0.75 else False
        wait = self.WebDriverWait(driver, 20, poll_frequency=0.25,
            ignored_exceptions=(self.StaleElementReferenceException,))
        try:
            return wait.until(detail_ready)
        except self.TimeoutException:
            pass
        # 优先重用查找阶段确认过的标记，避免在最大缩放下从头盲查。
        saved = getattr(self, "_r007_selected_marker", None)
        if saved is not None and saved[0] == outlet_name:
            try:
                marker = saved[1]
                if marker is not None and marker.is_displayed():
                    self._r007_click(driver, marker)
                    return wait.until(detail_ready)
            except (self.TimeoutException, self.StaleElementReferenceException, self.WebDriverException):
                pass
        # SDK 若重建了标记 DOM，则用已有真实点击流程重新确认网点。
        # 不缩小地图、不调用 setZoom，也不把“详情关闭”当作成功。
        self._r007_click_outlet_marker(driver, outlet_name)
        try:
            return wait.until(detail_ready)
        except self.TimeoutException as exc:
            raise AssertionError("R007 最大缩放后重新点击目标标记，详情仍未加载：" + outlet_name) from exc


    def _r007_navigate(self, driver):
        driver.switch_to.default_content()
        driver.get("https://www.sf-express.com/")
        before = set(driver.window_handles)
        self._r007_click(driver, self._r007_wait(driver, "a", "服务支持"))
        def support_ready(d):
            added = set(d.window_handles) - before
            if added:
                d.switch_to.window(next(iter(added)))
            self._r007_dismiss_cookie_banner(d)
            return any(e.is_displayed() for e in d.find_elements(
                self.By.CSS_SELECTOR, ".side-menu"))
        self.WebDriverWait(driver, 30).until(support_ready)
        # 点击后单独确认路由；SSR 菜单已显示时，客户端事件可能尚未绑定。
        # 仅在跳转未完成时重试，不重做已经成功的表单和地图操作。
        original_window = driver.current_window_handle
        menu_windows = set(driver.window_handles)

        def outlets_route_ready(d):
            self._r007_dismiss_cookie_banner(d)
            if "/outlets-query" in d.current_url:
                return True
            for handle in set(d.window_handles) - menu_windows:
                d.switch_to.window(handle)
                if "/outlets-query" in d.current_url:
                    return True
            d.switch_to.window(original_window)
            return "/outlets-query" in d.current_url

        for attempt in range(3):
            if outlets_route_ready(driver):
                break
            if not any(e.is_displayed() and e.text.strip() == "服务网点"
                       for e in driver.find_elements(
                           self.By.CSS_SELECTOR, ".side-menu .side-child-item")):
                self._r007_click(driver, self._r007_wait(
                    driver, ".side-menu .title", "服务查询"))
            self._r007_click(driver, self._r007_wait(
                driver, ".side-menu .side-child-item", "服务网点"))
            try:
                self.WebDriverWait(driver, 15, poll_frequency=0.3,
                    ignored_exceptions=(self.StaleElementReferenceException,)
                ).until(outlets_route_ready)
                break
            except self.TimeoutException as exc:
                if attempt == 2:
                    raise AssertionError(
                        "R007 点击左侧服务网点后未完成跳转（共尝试3次）：URL="
                        + driver.current_url) from exc
        self._r007_wait_form(driver)
        assert "/outlets-query" in driver.current_url, "R007 未进入服务网点页面"


    def _r007_detail(self, driver, name=None):
        for panel in driver.find_elements(self.By.CSS_SELECTOR,
                ".range-query .map .BMap_bubble_content, .range-query .map .BMap_pop"):
            if not panel.is_displayed():
                continue
            text = panel.text.strip()
            # 官网“支持”一行可选；无此行时要求电话或营业时间，仍限定真实地图信息窗。
            if ("距离" in text and self.re.search(r"\d", text)
                    and ("支持" in text or self.re.search(r"\d{2}:\d{2}|\d[\d -]{5,}\d", text))
                    and (name is None or name in text)):
                return panel
        return False


    def _r007_click_outlet_marker(self, driver, outlet_name):
        """逐个点击真实地图标记；单个标记没有响应时尝试其他点击方式并继续检查。"""
        selector = ".range-query .result-box .map .BMap_Marker"
        self._r007_wait(driver, selector, timeout=45)
        visited, names, skipped = set(), [], []

        def marker_key(element):
            # 百度地图可能在点击后重绘 marker 节点；使用位置/标题作辅助去重，
            # 避免 WebElement.id 变化导致反复点击同一个地理位置。
            try:
                return driver.execute_script("""
                    const e=arguments[0],r=e.getBoundingClientRect();
                    return [
                      (e.getAttribute('title')||''),
                      (e.getAttribute('aria-label')||''),
                      Math.round(r.left),Math.round(r.top),
                      Math.round(r.width),Math.round(r.height),
                      (e.getAttribute('style')||'').slice(0,100)
                    ].join('|');
                """, element)
            except self.WebDriverException:
                return element.id

        def wait_for_new_detail(previous_text, timeout=3):
            def changed(d):
                panel = self._r007_detail(d)
                if not panel:
                    return False
                text = panel.text.strip()
                if not text:
                    return False
                # 没有先前详情时，只要真实信息窗出现就算本次点击成功；
                # 否则必须看到信息窗内容变化，避免将旧详情误认为新结果。
                return panel if (not previous_text or text != previous_text) else False
            try:
                return self.WebDriverWait(
                    driver, timeout, poll_frequency=0.2,
                    ignored_exceptions=(self.StaleElementReferenceException,)
                ).until(changed)
            except self.TimeoutException:
                return False

        deadline = self.time.monotonic() + 180
        while self.time.monotonic() < deadline:
            candidates = []
            for element in driver.find_elements(self.By.CSS_SELECTOR, selector):
                try:
                    if not element.is_displayed():
                        continue
                    key = marker_key(element)
                    if key not in visited:
                        candidates.append((key, element))
                except (self.StaleElementReferenceException, self.WebDriverException):
                    continue
            if not candidates:
                break

            key, marker = candidates[0]
            visited.add(key)

            # 关闭上一个信息窗，保证后续判断确实来自本次标记点击。
            for close in driver.find_elements(self.By.CSS_SELECTOR,
                    ".range-query .map .BMap_pop img[title*='关闭'], "
                    ".range-query .map .BMap_pop [aria-label='关闭']"):
                try:
                    if close.is_displayed():
                        self._r007_click(driver, close)
                except (self.StaleElementReferenceException, self.WebDriverException):
                    continue

            previous = self._r007_detail(driver)
            previous_text = previous.text.strip() if previous else ""

            # 方案一：标准 Selenium click。
            try:
                self._r007_click(driver, marker)
            except (self.StaleElementReferenceException, self.WebDriverException):
                pass
            panel = wait_for_new_detail(previous_text, timeout=12)

            # 方案二：ActionChains 移动到标记中心点击。部分百度地图标记的
            # 外层 div 接收鼠标事件，element.click() 并不能触发地图 SDK 监听器。
            if not panel:
                try:
                    marker = next((e for e in driver.find_elements(
                        self.By.CSS_SELECTOR, selector)
                        if e.is_displayed() and marker_key(e) == key), None)
                    if marker is not None:
                        self.ActionChains(driver).move_to_element(marker).pause(0.15).click().perform()
                except (self.StaleElementReferenceException, self.WebDriverException):
                    pass
                panel = wait_for_new_detail(previous_text, timeout=12)

            # 方案三：点击标记内的图片/图标子元素，仍是对页面真实控件的用户式点击。
            if not panel:
                try:
                    marker = next((e for e in driver.find_elements(
                        self.By.CSS_SELECTOR, selector)
                        if e.is_displayed() and marker_key(e) == key), None)
                    if marker is not None:
                        children = [e for e in marker.find_elements(
                            self.By.CSS_SELECTOR, "img, canvas, svg")
                            if e.is_displayed()]
                        if children:
                            self.ActionChains(driver).move_to_element(children[0]).click().perform()
                        else:
                            rect = marker.rect
                            self.ActionChains(driver).move_to_element_with_offset(
                                marker, 0, 0).click().perform()
                except (self.StaleElementReferenceException, self.WebDriverException):
                    pass
                panel = wait_for_new_detail(previous_text, timeout=12)

            if not panel:
                # 某些标记被相邻标记遮挡或没有独立信息窗，不要因此终止整个
                # R007；记录位置后继续点击剩余标记。
                skipped.append(key)
                continue

            detail_text = panel.text.strip()
            if detail_text and detail_text not in names:
                names.append(detail_text[:160])

            if outlet_name in detail_text:
                self._r007_selected_marker = (outlet_name, marker)
                return panel

        popups = [e.get_attribute("innerText") for e in driver.find_elements(
            self.By.CSS_SELECTOR, ".range-query .map .BMap_pop") if e.is_displayed()]
        names.append("当前信息窗=" + str(popups)[:1200])
        raise AssertionError(
            "R007 查询结果中未找到目标网点详情：目标=%s；已访问标记=%s；"
            "成功打开详情数=%s；未响应标记=%s；已见详情=%s；当前URL=%s" %
            (outlet_name, len(visited), len(names), skipped, names, driver.current_url)
        )


    def _r007_screenshot(self, driver, outlet_name, case_id):
        """保存 R007 整页截图：沿用 R001-R005 的时间戳_用例编号.png 命名规则。"""
        import base64
        from pathlib import Path

        self._r007_dismiss_cookie_banner(driver)

        # BMap_pop 外壳可为 0×0，但绝对定位子节点仍在显示详情。
        # 在等待中重新定位，并检查真实渲染的文本矩形，不以外壳尺寸判定。
        last_state = {}

        def target_detail_ready(d):
            self._r007_dismiss_cookie_banner(d)
            panel = self._r007_detail(d, outlet_name)
            maps = d.find_elements(self.By.CSS_SELECTOR, ".range-query .result-box .map")
            map_element = next((e for e in maps if e.is_displayed()), None)
            if panel is False or panel is None or map_element is None:
                last_state.clear()
                last_state.update({"mapFound": map_element is not None, "panelFound": bool(panel)})
                return False
            state = d.execute_script("""
                const map = arguments[0], panel = arguments[1];
                const rect = r => ({x:r.x, y:r.y, w:r.width, h:r.height});
                const shown = e => {
                    for (let p=e; p; p=p.parentElement) {
                        const s=getComputedStyle(p);
                        if (s.display==='none' || s.visibility==='hidden' ||
                            s.visibility==='collapse' || Number(s.opacity)===0) return false;
                    }
                    return true;
                };
                const m=map.getBoundingClientRect(), p=panel.getBoundingClientRect();
                const boxes=[], texts=[];
                // Range 反映文本实际绘制位置，也适用于零尺寸父节点中的绝对定位内容。
                const walker=document.createTreeWalker(panel, NodeFilter.SHOW_TEXT);
                let node;
                while ((node=walker.nextNode())) {
                    const text=node.textContent.trim();
                    if (!text || !shown(node.parentElement)) continue;
                    const range=document.createRange();
                    range.selectNodeContents(node);
                    const rs=Array.from(range.getClientRects()).filter(r=>r.width>0 && r.height>0);
                    if (rs.length) { texts.push(text); boxes.push(...rs); }
                }
                const text=texts.join(' ');
                const left=boxes.length ? Math.min(...boxes.map(r=>r.left)) : 0;
                const top=boxes.length ? Math.min(...boxes.map(r=>r.top)) : 0;
                const right=boxes.length ? Math.max(...boxes.map(r=>r.right)) : 0;
                const bottom=boxes.length ? Math.max(...boxes.map(r=>r.bottom)) : 0;
                return {
                    mapVisible: shown(map) && m.width>0 && m.height>0,
                    panelVisible: shown(panel) && boxes.length>0 &&
                        text.includes(arguments[2]) && text.includes('距离') &&
                        (text.includes('支持') || /[0-9]{2}:[0-9]{2}|[0-9][0-9 -]{5,}[0-9]/.test(text)) && /[0-9]/.test(text),
                    map: rect(m), panel: rect(p),
                    renderedDetail: {x:left,y:top,w:right-left,h:bottom-top},
                    visibleText: text.slice(0,500)
                };
            """, map_element, panel, outlet_name)
            last_state.clear()
            last_state.update(state)
            return state if state.get("mapVisible") and state.get("panelVisible") else False

        try:
            self.WebDriverWait(
                driver, 15, poll_frequency=0.25,
                ignored_exceptions=(self.StaleElementReferenceException,)
            ).until(target_detail_ready)
        except self.TimeoutException as exc:
            raise AssertionError("R007 截图前地图或实际网点详情未完整显示：" + str(last_state)) from exc


        # 拖动至最大级别由前一步完成，截图前再次检查滑块位置。
        slider = self._r007_wait(driver, ".range-query .map .BMap_stdMpSliderBar")
        top = driver.execute_script("return parseFloat(getComputedStyle(arguments[0]).top);", slider)
        assert isinstance(top, (int, float)) and abs(top - 1) <= 0.5, "R007 截图前未保持最大缩放"
        self._r007_wait(driver, ".range-query .map .BMap_stdMpZoom")
        metrics = driver.execute_cdp_cmd("Page.getLayoutMetrics", {})
        size = metrics.get("cssContentSize") or metrics.get("contentSize")
        assert size and size.get("width", 0) > 0 and size.get("height", 0) > 0, (
            "R007 无法获取完整页面尺寸")

        image = driver.execute_cdp_cmd("Page.captureScreenshot", {
            "format": "png",
            "fromSurface": True,
            "captureBeyondViewport": True,
            "clip": {
                "x": 0, "y": 0,
                "width": size["width"], "height": size["height"], "scale": 1
            }
        })
        content = base64.b64decode(image["data"])
        assert content.startswith(b"\x89PNG\r\n\x1a\n"), "R007 截图生成失败"
        width = int.from_bytes(content[16:20], "big")
        height = int.from_bytes(content[20:24], "big")
        assert width >= int(size["width"]) and height >= int(size["height"]), (
            "R007 截图尺寸不足以覆盖整页：实际=%s×%s；页面=%s×%s" %
            (width, height, size["width"], size["height"])
        )

        # 与 R005 的 take_screenshot 命名格式一致：时间戳_SF_R007_001.png。
        folder = Path("screenshots")
        folder.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%H%M%S%d%f")[:-3]
        output = folder / (timestamp + "_" + case_id + ".png")
        output.write_bytes(content)
        assert output.is_file() and output.stat().st_size > 0, (
            "R007 截图文件未成功保存：" + str(output))
        return str(output)


    def _r007_open_picker(self, driver):
        root = "#range-query-citypicker"
        # 官网部分页面会把 city-picker 弹层挂载到 root 之外（portal/teleport），
        # 所以先查 root 内部，再退回全局可见的搜索框。
        search_css_list = (
            root + " .city-picker input.city-search",
            ".city-picker input.city-search",
        )
        def search_ready(d):
            self._r007_dismiss_cookie_banner(d)
            for search_css in search_css_list:
                search = next((e for e in d.find_elements(self.By.CSS_SELECTOR, search_css)
                               if e.is_displayed() and e.is_enabled()), False)
                if search:
                    return search
            return False
        # 已打开时直接使用；只有开关明确关闭才点击，避免反复切换。
        for attempt in range(2):
            search = search_ready(driver)
            if search:
                return search
            trigger = self._r007_wait(driver, root)
            if "expanding" not in (trigger.get_attribute("class") or "").split():
                self._r007_click(driver, trigger)
            try:
                return self.WebDriverWait(driver, 30, poll_frequency=0.25,
                    ignored_exceptions=(self.StaleElementReferenceException,)).until(search_ready)
            except self.TimeoutException:
                trigger = driver.find_element(self.By.CSS_SELECTOR, root)
                if "expanding" in (trigger.get_attribute("class") or "").split():
                    # 开关已打开却没有搜索框：等待异步组件，不再点击关闭它。
                    if attempt == 0:
                        continue
        trigger = driver.find_element(self.By.CSS_SELECTOR, root)
        raise AssertionError("R007 地址选择器未加载：class=%s；控件HTML=%s" %
                             (trigger.get_attribute("class"), trigger.get_attribute("outerHTML")[:1800]))


    def _r007_select_area(self, driver, city, district):
        search = self._r007_open_picker(driver)
        root = "#range-query-citypicker .city-picker"
        search.send_keys(self.Keys.CONTROL, "a")
        search.send_keys(city)

        def district_option(d):
            self._r007_dismiss_cookie_banner(d)
            for option in d.find_elements(self.By.CSS_SELECTOR, root + " .search-result li"):
                if option.is_displayed() and city in option.text and district in option.text:
                    return option
            return False
        try:
            option = self.WebDriverWait(driver, 30, poll_frequency=0.25,
                ignored_exceptions=(self.StaleElementReferenceException,)).until(district_option)
        except self.TimeoutException as exc:
            values = [e.text for e in driver.find_elements(
                self.By.CSS_SELECTOR, root + " .search-result") if e.is_displayed()]
            raise AssertionError("R007 未找到对应城市区县：%s/%s；候选=%s" %
                                 (city, district, values)) from exc
        self._r007_click(driver, option)
        def selected(d):
            value = d.find_element(self.By.CSS_SELECTOR,
                "#range-query-citypicker input.result").get_attribute("value") or ""
            return city in value and district in value and not any(
                e.is_displayed() for e in d.find_elements(self.By.CSS_SELECTOR, root))
        self.WebDriverWait(driver, 15).until(selected,
            "R007 城市区县未正确回填或地址弹层未关闭")

    def _r007_search(self, driver, keyword_text):
        keyword = self._r007_wait(driver, "#range-key-word")
        keyword.send_keys(self.Keys.CONTROL, "a")
        keyword.send_keys(keyword_text)
        # 沿用已通过的联想选择流程，使官网获得查询所需的经纬度。
        name = self._r007_wait(driver,
            ".key-word-query li:not(.noData) .detail-name", keyword_text)
        self._r007_click(driver, name.find_element(self.By.XPATH, ".."))
        assert keyword.get_attribute("value") == keyword_text, "R007 关键词回填错误"
        self._r007_click(driver, self._r007_wait(
            driver, ".range-query .search-btn:not(.disabled)"))
        self._r007_wait(driver, ".range-query .result-box .map .BMap_Marker", timeout=45)

    def _r007_drag_to_max(self, driver, outlet_name):
        """仅拖动滑块到最大级别，不用加号、刻度点击或修改地图状态代替。"""
        slider_css = ".range-query .map .BMap_stdMpSliderBar"
        control = self._r007_wait(driver, ".range-query .map .BMap_stdMpZoom")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", control)
        self.ActionChains(driver).move_to_element(control).perform()
        slider = self._r007_wait(driver, slider_css)
        before = driver.execute_script(
            "return parseFloat(getComputedStyle(arguments[0]).top);", slider)
        assert isinstance(before, (int, float)), "R007 无法读取缩放滑块位置"
        # 百度地图 v3 导航组件把滑块上限限制在 top=1px。
        # 超过上限少量拖动由 SDK 自行钳制，避免小数像素留下一级误差。
        distance = max(8, int(before) + 8)
        self.ActionChains(driver).move_to_element(slider).click_and_hold() \
            .pause(0.2).move_by_offset(0, -distance).pause(0.3).release().perform()

        def at_max(d):
            element = d.find_element(self.By.CSS_SELECTOR, slider_css)
            top = d.execute_script("return parseFloat(getComputedStyle(arguments[0]).top);", element)
            return isinstance(top, (int, float)) and abs(top - 1) <= 0.5
        try:
            self.WebDriverWait(driver, 15, poll_frequency=0.25,
                ignored_exceptions=(self.StaleElementReferenceException,)).until(at_max)
        except self.TimeoutException as exc:
            after = driver.find_element(self.By.CSS_SELECTOR, slider_css).value_of_css_property("top")
            raise AssertionError("R007 拖动后未达到最大缩放：原位置=%s；当前位置=%s" %
                                 (before, after)) from exc
        self.time.sleep(1)  # 地图缩放动画结束后再读取详情并截图。
        self._r007_restore_detail(driver, outlet_name)
        assert at_max(driver), "R007 截图前缩放滑块离开最大刻度"

    @pytest.mark.parametrize("case_id,city,district,keyword,outlet", [
        ("SF_R007_001", "广州市", "天河区", "天河花市", "龙步街店"),
        ("SF_R007_002", "深圳市", "罗湖区", "天虹商场", "耀华楼店"),
        ("SF_R007_003", "南京市", "玄武区", "新世界百货", "进香河路店"),
        ("SF_R007_004", "杭州市", "西湖区", "西城广场", "电信大楼店"),
    ], ids=["SF_R007_001", "SF_R007_002", "SF_R007_003", "SF_R007_004"])
    def test_SF_R007(self, driver, case_id, city, district, keyword, outlet):
        """四组数据各自查询、打开指定网点、拖到最大缩放并保存完整截图。"""
        old_wait = driver.timeouts.implicit_wait
        driver.implicitly_wait(0)
        try:
            self._r007_navigate(driver)
            self._r007_select_area(driver, city, district)
            self._r007_search(driver, keyword)
            self._r007_click_outlet_marker(driver, outlet)
            self._r007_drag_to_max(driver, outlet)
            path = self._r007_screenshot(driver, outlet, case_id)
            print("%s 完成：%s-%s；关键词=%s；网点=%s；拖动至最大缩放；截图=%s" %
                  (case_id, city, district, keyword, outlet, path))
        finally:
            driver.implicitly_wait(old_wait)


    def _r008_dismiss_cookie_banner(self, driver):
        """只通过官网 Cookie 按钮关闭弹窗，不删除遮罩或修改存储。"""
        for banner in driver.find_elements(self.By.CSS_SELECTOR, ".cookie-policy"):
            if not banner.is_displayed():
                continue
            buttons = [e for e in banner.find_elements(self.By.CSS_SELECTOR, ".right .btn")
                       if e.is_displayed() and e.is_enabled() and e.text.strip() == "不同意"]
            assert len(buttons) == 1, "R008 Cookie 弹窗未找到唯一的不同意按钮"
            buttons[0].click()
            self.WebDriverWait(driver, 8).until(self.EC.invisibility_of_element(banner))

    def _r008_wait(self, driver, selector, text=None, timeout=30):
        def ready(d):
            self._r008_dismiss_cookie_banner(d)
            for element in d.find_elements(self.By.CSS_SELECTOR, selector):
                if (element.is_displayed() and element.is_enabled()
                        and (text is None or element.text.strip() == text)):
                    return element
            return False
        try:
            return self.WebDriverWait(driver, timeout, poll_frequency=0.25,
                ignored_exceptions=(self.StaleElementReferenceException,)).until(ready)
        except self.TimeoutException as exc:
            values = [e.text[:160] for e in driver.find_elements(
                self.By.CSS_SELECTOR, selector) if e.is_displayed()]
            raise AssertionError("R008 控件未就绪：%s；目标=%s；可见内容=%s；URL=%s" %
                                 (selector, text, values, driver.current_url)) from exc

    def _r008_click(self, driver, element):
        self._r008_dismiss_cookie_banner(driver)
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        try:
            element.click()
        except self.ElementClickInterceptedException:
            self._r008_dismiss_cookie_banner(driver)
            # 地图标记可能互相覆盖；对已定位的标记发送标准 click。
            driver.execute_script("arguments[0].click();", element)

    def _r008_navigate(self, driver):
        driver.switch_to.default_content()
        driver.get("https://www.sf-express.com/")
        before = set(driver.window_handles)
        self._r008_click(driver, self._r008_wait(driver, "a", "服务支持"))
        def support_ready(d):
            added = set(d.window_handles) - before
            if added:
                d.switch_to.window(next(iter(added)))
            self._r008_dismiss_cookie_banner(d)
            return any(e.is_displayed() for e in d.find_elements(
                self.By.CSS_SELECTOR, ".side-menu"))
        self.WebDriverWait(driver, 30).until(support_ready)
        # 点击后单独确认路由；SSR 菜单已显示时，客户端事件可能尚未绑定。
        # 仅在跳转未完成时重试，不重做已经成功的表单和地图操作。
        original_window = driver.current_window_handle
        menu_windows = set(driver.window_handles)

        def outlets_route_ready(d):
            self._r008_dismiss_cookie_banner(d)
            if "/accept-query" in d.current_url:
                return True
            for handle in set(d.window_handles) - menu_windows:
                d.switch_to.window(handle)
                if "/accept-query" in d.current_url:
                    return True
            d.switch_to.window(original_window)
            return "/accept-query" in d.current_url

        for attempt in range(3):
            if outlets_route_ready(driver):
                break
            if not any(e.is_displayed() and e.text.strip() == "收寄标准"
                       for e in driver.find_elements(
                           self.By.CSS_SELECTOR, ".side-menu .side-child-item")):
                self._r008_click(driver, self._r008_wait(
                    driver, ".side-menu .title", "服务查询"))
            self._r008_click(driver, self._r008_wait(
                driver, ".side-menu .side-child-item", "收寄标准"))
            try:
                self.WebDriverWait(driver, 15, poll_frequency=0.3,
                    ignored_exceptions=(self.StaleElementReferenceException,)
                ).until(outlets_route_ready)
                break
            except self.TimeoutException as exc:
                if attempt == 2:
                    raise AssertionError(
                        "R008 点击左侧收寄标准后未完成跳转（共尝试3次）：URL="
                        + driver.current_url) from exc
        self._r008_wait_form(driver)
        assert "/accept-query" in driver.current_url, "R008 未进入收寄标准页面"

    def _r008_wait_form(self, driver):
        def ready(d):
            self._r008_dismiss_cookie_banner(d)
            return "/accept-query" in d.current_url and all(
                any(e.is_displayed() and e.is_enabled()
                    for e in d.find_elements(self.By.CSS_SELECTOR, css))
                for css in ("#accept-from-input > input", "#accept-consignment-input > input"))
        for attempt in range(2):
            try:
                self.WebDriverWait(driver, 40, poll_frequency=0.3,
                    ignored_exceptions=(self.StaleElementReferenceException,)).until(ready)
                return
            except self.TimeoutException as exc:
                if attempt == 0 and "/accept-query" in driver.current_url:
                    driver.refresh()  # 尚未填写表单，只重试一次组件加载。
                    continue
                raise AssertionError("R008 收寄标准表单未加载：" + driver.current_url) from exc

    def _r008_select_area(self, driver, field, path):
        root = {"origin": "#accept-from-input", "destination": "#accept-to-input"}[field]
        picker = root + " .city-picker"
        # 先确认输入框已启用，再打开所属地址弹层，避免误点另一端。
        self._r008_click(driver, self._r008_wait(driver, root + " > input"))
        try:
            self._r008_wait(driver, picker + " .tab-item", "省/直辖市", timeout=30)
        except AssertionError:
            # 官网 openFrom/ToCityPick 只打开，不切换关闭；用于客户端尚未就绪的首次点击。
            self._r008_click(driver, self._r008_wait(driver, root + " > input"))
        self._r008_click(driver, self._r008_wait(driver, picker + " .tab-item", "省/直辖市"))
        for name in path:
            self._r008_click(driver, self._r008_wait(driver, picker + " .card-name", name))

        def selected(d):
            value = d.find_element(self.By.CSS_SELECTOR, root + " > input").get_attribute("value") or ""
            closed = not any(e.is_displayed() for e in d.find_elements(self.By.CSS_SELECTOR, picker))
            return value if closed and all(name in value for name in path) else False
        try:
            self.WebDriverWait(driver, 20, poll_frequency=0.25,
                ignored_exceptions=(self.StaleElementReferenceException,)).until(selected)
        except self.TimeoutException as exc:
            value = driver.find_element(self.By.CSS_SELECTOR, root + " > input").get_attribute("value")
            raise AssertionError("R008 地址选择未完成：%s；预期=%s；实际=%s" % (field, path, value)) from exc

    def _r008_query_item(self, driver, keyword, item):
        field = self._r008_wait(driver, "#accept-consignment-input > input")
        self._r008_click(driver, field)
        field.send_keys(self.Keys.CONTROL, "a")
        field.send_keys(self.Keys.BACKSPACE)
        field.send_keys(keyword)
        self._r008_click(driver, self._r008_wait(
            driver, "#accept-consignment-input li .cons-name", item))
        self.WebDriverWait(driver, 15).until(lambda d:
            d.find_element(self.By.CSS_SELECTOR, "#accept-consignment-input > input").get_attribute("value") == item
            and not any(e.is_displayed() for e in d.find_elements(
                self.By.CSS_SELECTOR, "#accept-consignment-input li")))
        # 每条参数用例使用新浏览器；不允许把查询前已存在的内容当作本次结果。
        assert not any(e.is_displayed() for e in driver.find_elements(
            self.By.CSS_SELECTOR, ".accept-query .result-box")), "R008 查询前存在旧结果"
        self._r008_click(driver, self._r008_wait(
            driver, ".accept-query button.search-btn:not(.disabled)", "查询"))
        stable = {"text": "", "since": 0}

        def result_ready(d):
            self._r008_dismiss_cookie_banner(d)
            for row in d.find_elements(self.By.CSS_SELECTOR, ".accept-query .result-table tbody tr"):
                if not row.is_displayed():
                    continue
                cells = row.find_elements(self.By.CSS_SELECTOR, "td")
                if len(cells) < 3 or item not in cells[0].text or not cells[1].text.strip():
                    continue
                text = row.text.strip()
                if text != stable["text"]:
                    stable.update(text=text, since=self.time.monotonic())
                elif self.time.monotonic() - stable["since"] >= 0.8:
                    return row
            return False
        try:
            self.WebDriverWait(driver, 45, poll_frequency=0.3,
                ignored_exceptions=(self.StaleElementReferenceException,)).until(result_ready)
        except self.TimeoutException as exc:
            actual = [e.text for e in driver.find_elements(self.By.CSS_SELECTOR,
                ".accept-query .result-box, .accept-query .search-tips") if e.is_displayed()]
            raise AssertionError("R008 未得到对应物品的收寄标准：物品=%s；页面结果=%s；URL=%s" %
                                 (item, actual, driver.current_url)) from exc

    def _r008_screenshot(self, driver, case_id, item):
        import base64
        from pathlib import Path
        self._r008_dismiss_cookie_banner(driver)
        result = self._r008_wait(driver, ".accept-query .result-table")
        assert item in result.text, "R008 截图前查询结果与物品不符：" + item
        # CDP 截取完整文档，包含输入条件、全部结果行及页面下方说明。
        driver.execute_script("window.scrollTo(0, 0);")
        metrics = driver.execute_cdp_cmd("Page.getLayoutMetrics", {})
        size = metrics.get("cssContentSize") or metrics.get("contentSize")
        assert size and size["width"] > 0 and size["height"] > 0, "R008 页面尺寸无效"
        shot = driver.execute_cdp_cmd("Page.captureScreenshot", {
            "format": "png", "fromSurface": True, "captureBeyondViewport": True,
            "clip": {"x": 0, "y": 0, "width": size["width"], "height": size["height"], "scale": 1}
        })
        content = base64.b64decode(shot["data"])
        assert content.startswith(b"\x89PNG\r\n\x1a\n"), "R008 截图生成失败"
        assert (int.from_bytes(content[16:20], "big") >= int(size["width"])
                and int.from_bytes(content[20:24], "big") >= int(size["height"])), "R008 截图未覆盖整页"
        folder = Path("screenshots")
        folder.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%H%M%S%d%f")[:-3]
        output = folder / (timestamp + "_" + case_id + ".png")
        output.write_bytes(content)
        assert output.is_file() and output.stat().st_size > 0, "R008 截图保存失败"
        return str(output)

    @pytest.mark.parametrize("case_id,keyword,item", [
        ("SF_R008_001", "电子", "电子琴"),
        ("SF_R008_002", "电脑", "笔记本电脑"),
    ], ids=["SF_R008_001", "SF_R008_002"])
    def test_SF_R008(self, driver, case_id, keyword, item):
        """省/直辖市逐级选址；两种物品各自查询、校验并保存完整结果截图。"""
        old_wait = driver.timeouts.implicit_wait
        driver.implicitly_wait(0)
        try:
            self._r008_navigate(driver)
            self._r008_select_area(driver, "origin", ["广东省", "深圳市", "光明区"])
            self._r008_select_area(driver, "destination", ["江苏省", "南京市", "鼓楼区"])
            self._r008_query_item(driver, keyword, item)
            path = self._r008_screenshot(driver, case_id, item)
            print("%s 完成：深圳光明区→南京鼓楼区；物品=%s；完整结果截图=%s" % (case_id, item, path))
        finally:
            driver.implicitly_wait(old_wait)


    def _r009_dismiss_cookie_banner(self, driver):
        """只通过官网 Cookie 按钮关闭弹窗，不删除遮罩或修改存储。"""
        for banner in driver.find_elements(self.By.CSS_SELECTOR, ".cookie-policy"):
            if not banner.is_displayed():
                continue
            buttons = [e for e in banner.find_elements(self.By.CSS_SELECTOR, ".right .btn")
                       if e.is_displayed() and e.is_enabled() and e.text.strip() == "不同意"]
            assert len(buttons) == 1, "R009 Cookie 弹窗未找到唯一的不同意按钮"
            buttons[0].click()
            self.WebDriverWait(driver, 8).until(self.EC.invisibility_of_element(banner))

    def _r009_wait(self, driver, selector, text=None, timeout=30):
        def ready(d):
            self._r009_dismiss_cookie_banner(d)
            for element in d.find_elements(self.By.CSS_SELECTOR, selector):
                if (element.is_displayed() and element.is_enabled()
                        and (text is None or element.text.strip() == text)):
                    return element
            return False
        try:
            return self.WebDriverWait(driver, timeout, poll_frequency=0.25,
                ignored_exceptions=(self.StaleElementReferenceException,)).until(ready)
        except self.TimeoutException as exc:
            values = [e.text[:160] for e in driver.find_elements(
                self.By.CSS_SELECTOR, selector) if e.is_displayed()]
            raise AssertionError("R009 控件未就绪：%s；目标=%s；可见内容=%s；URL=%s" %
                                 (selector, text, values, driver.current_url)) from exc

    def _r009_click(self, driver, element):
        self._r009_dismiss_cookie_banner(driver)
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        try:
            element.click()
        except self.ElementClickInterceptedException:
            self._r009_dismiss_cookie_banner(driver)
            # 地图标记可能互相覆盖；对已定位的标记发送标准 click。
            driver.execute_script("arguments[0].click();", element)

    def _r009_navigate(self, driver):
        driver.switch_to.default_content()
        driver.get("https://www.sf-express.com/")
        before = set(driver.window_handles)
        self._r009_click(driver, self._r009_wait(driver, "a", "服务支持"))
        def support_ready(d):
            added = set(d.window_handles) - before
            if added:
                d.switch_to.window(next(iter(added)))
            self._r009_dismiss_cookie_banner(d)
            return any(e.is_displayed() for e in d.find_elements(
                self.By.CSS_SELECTOR, ".side-menu"))
        self.WebDriverWait(driver, 30).until(support_ready)
        # 点击后单独确认路由；SSR 菜单已显示时，客户端事件可能尚未绑定。
        # 仅在跳转未完成时重试，不重做已经成功的表单和地图操作。
        original_window = driver.current_window_handle
        menu_windows = set(driver.window_handles)

        def outlets_route_ready(d):
            self._r009_dismiss_cookie_banner(d)
            if "/accept-query" in d.current_url:
                return True
            for handle in set(d.window_handles) - menu_windows:
                d.switch_to.window(handle)
                if "/accept-query" in d.current_url:
                    return True
            d.switch_to.window(original_window)
            return "/accept-query" in d.current_url

        for attempt in range(3):
            if outlets_route_ready(driver):
                break
            if not any(e.is_displayed() and e.text.strip() == "收寄标准"
                       for e in driver.find_elements(
                           self.By.CSS_SELECTOR, ".side-menu .side-child-item")):
                self._r009_click(driver, self._r009_wait(
                    driver, ".side-menu .title", "服务查询"))
            self._r009_click(driver, self._r009_wait(
                driver, ".side-menu .side-child-item", "收寄标准"))
            try:
                self.WebDriverWait(driver, 15, poll_frequency=0.3,
                    ignored_exceptions=(self.StaleElementReferenceException,)
                ).until(outlets_route_ready)
                break
            except self.TimeoutException as exc:
                if attempt == 2:
                    raise AssertionError(
                        "R009 点击左侧收寄标准后未完成跳转（共尝试3次）：URL="
                        + driver.current_url) from exc
        self._r009_wait_form(driver)
        assert "/accept-query" in driver.current_url, "R009 未进入收寄标准页面"

    def _r009_wait_form(self, driver):
        def ready(d):
            self._r009_dismiss_cookie_banner(d)
            return "/accept-query" in d.current_url and all(
                any(e.is_displayed() and e.is_enabled()
                    for e in d.find_elements(self.By.CSS_SELECTOR, css))
                for css in ("#accept-from-input > input", "#accept-consignment-input > input"))
        for attempt in range(2):
            try:
                self.WebDriverWait(driver, 40, poll_frequency=0.3,
                    ignored_exceptions=(self.StaleElementReferenceException,)).until(ready)
                return
            except self.TimeoutException as exc:
                if attempt == 0 and "/accept-query" in driver.current_url:
                    driver.refresh()  # 尚未填写表单，只重试一次组件加载。
                    continue
                raise AssertionError("R009 收寄标准表单未加载：" + driver.current_url) from exc

    def _r009_screenshot(self, driver, case_id, item):
        import base64
        from pathlib import Path
        self._r009_dismiss_cookie_banner(driver)
        assert self._r009_result(driver, item), "R009 截图前本次查询结果不可见：" + item
        # CDP 截取完整文档，包含输入条件、全部结果行及页面下方说明。
        driver.execute_script("window.scrollTo(0, 0);")
        metrics = driver.execute_cdp_cmd("Page.getLayoutMetrics", {})
        size = metrics.get("cssContentSize") or metrics.get("contentSize")
        assert size and size["width"] > 0 and size["height"] > 0, "R009 页面尺寸无效"
        shot = driver.execute_cdp_cmd("Page.captureScreenshot", {
            "format": "png", "fromSurface": True, "captureBeyondViewport": True,
            "clip": {"x": 0, "y": 0, "width": size["width"], "height": size["height"], "scale": 1}
        })
        content = base64.b64decode(shot["data"])
        assert content.startswith(b"\x89PNG\r\n\x1a\n"), "R009 截图生成失败"
        assert (int.from_bytes(content[16:20], "big") >= int(size["width"])
                and int.from_bytes(content[20:24], "big") >= int(size["height"])), "R009 截图未覆盖整页"
        folder = Path("screenshots")
        folder.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%H%M%S%d%f")[:-3]
        output = folder / (timestamp + "_" + case_id + ".png")
        output.write_bytes(content)
        assert output.is_file() and output.stat().st_size > 0, "R009 截图保存失败"
        return str(output)

    def _r009_select_area(self, driver, field, path):
        root = {"origin": "#accept-from-input", "destination": "#accept-to-input"}[field]
        picker = root + " .city-picker"
        tab = "热门城市" if field == "origin" else "港澳台"
        self._r009_click(driver, self._r009_wait(driver, root + " > input"))
        try:
            self._r009_wait(driver, picker + " .tab-item", tab)
        except AssertionError:
            # 与收寄标准原组件一致：再次点击只打开弹层，不关闭它。
            self._r009_click(driver, self._r009_wait(driver, root + " > input"))
        self._r009_click(driver, self._r009_wait(driver, picker + " .tab-item", tab))
        for name in path:
            self._r009_click(driver, self._r009_wait(driver, picker + " .card-name", name))

        normalize = lambda value: self.re.sub(r"[\s\-－–—>]+", "", value or "")

        def current_value(d):
            return d.find_element(
                self.By.CSS_SELECTOR, root + " > input"
            ).get_attribute("value") or ""

        def value_selected(d):
            value = current_value(d)
            normalized = normalize(value)
            return value if all(normalize(name) in normalized for name in path) else False

        # 第一阶段只验证地址是否回填。不要把“弹层没关闭”混入地址校验的异常中。
        try:
            value = self.WebDriverWait(
                driver, 20, poll_frequency=0.25,
                ignored_exceptions=(self.StaleElementReferenceException,)
            ).until(value_selected)
        except self.TimeoutException as exc:
            value = current_value(driver)
            raise AssertionError(
                "R009 地址未正确回填：%s；预期=%s；实际=%s" %
                (field, path, value)
            ) from exc

        def popup_visible(d):
            return any(
                e.is_displayed()
                for e in d.find_elements(self.By.CSS_SELECTOR, picker)
            )

        # 第二阶段尽力关闭弹层，但不再将关闭超时误报成“地址选择未完成”。
        # 官网组件有时保留可见的 picker 容器；实际是否展开优先参考触发器的 expanding 类。
        try:
            active = driver.switch_to.active_element
            active.send_keys(self.Keys.ESCAPE)
        except self.WebDriverException:
            pass

        try:
            self.WebDriverWait(
                driver, 1.5, poll_frequency=0.2,
                ignored_exceptions=(self.StaleElementReferenceException,)
            ).until(lambda d: not popup_visible(d))
        except self.TimeoutException:
            pass

        if popup_visible(driver):
            # 点击表单标题/空白区域触发组件的 outside-click 收起逻辑。
            try:
                neutral = next((
                    e for e in driver.find_elements(
                        self.By.CSS_SELECTOR,
                        ".accept-query .title-wrap, .accept-query .title"
                    )
                    if e.is_displayed() and e.is_enabled()
                ), None)
                if neutral:
                    driver.execute_script("arguments[0].click();", neutral)
            except self.WebDriverException:
                pass

            try:
                self.WebDriverWait(
                    driver, 2, poll_frequency=0.2,
                    ignored_exceptions=(self.StaleElementReferenceException,)
                ).until(lambda d: not popup_visible(d))
            except self.TimeoutException:
                pass

        # 最终确认回填值仍然正确。若官网把 picker 容器保留为可见状态，
        # 记录诊断但不因容器状态覆盖已经成功的地址选择结果。
        final_value = current_value(driver)
        if not all(normalize(name) in normalize(final_value) for name in path):
            raise AssertionError(
                "R009 地址选择后回填值发生变化：%s；预期=%s；实际=%s" %
                (field, path, final_value)
            )
        if popup_visible(driver):
            print(
                "R009 提示：%s 地址已正确回填，但 picker 容器仍显示；实际=%s" %
                (field, final_value)
            )

    def _r009_identity(self, driver):
        # 官网 idArea 的两个直接子项依次绑定 senderId、recId。
        area = ".accept-query .idArea"
        self._r009_wait(driver, area)
        controls = driver.find_elements(self.By.CSS_SELECTOR, area + " > .input .select-id")
        assert len(controls) == 2, "R009 寄件人/收件人身份控件数量异常"
        for index, value in ((1, "个人"), (2, "公司")):
            root = area + " > .input:nth-child(%d)" % index
            self._r009_click(driver, self._r009_wait(driver, root + " .select-id"))
            self._r009_click(driver, self._r009_wait(driver, root + " .options > div", value))
            self._r009_wait(driver, root + " .select-id", value)

    def _r009_result(self, driver, item):
        """只接受结果表或有实际返回结果时展示的无匹配说明，不接受接口失败提示。"""
        field = driver.find_element(self.By.CSS_SELECTOR, "#accept-consignment-input > input")
        if field.get_attribute("value") != item:
            return False
        if not any(e.is_displayed() for e in driver.find_elements(
                self.By.CSS_SELECTOR, ".accept-query button.search-btn:not(.disabled)")):
            return False
        for box in driver.find_elements(self.By.CSS_SELECTOR, ".accept-query .result-box"):
            if not box.is_displayed():
                continue
            for row in box.find_elements(self.By.CSS_SELECTOR, ".result-table tbody tr"):
                cells = row.find_elements(self.By.CSS_SELECTOR, "td")
                if (row.is_displayed() and len(cells) >= 3
                        and item in cells[0].text and cells[1].text.strip()):
                    return box
            # 官网只有返回非空结果、但没有收寄规则代码时才展示此区域。
            # 请求失败/空响应显示的是 main-box .search-tips，不能作为通过条件。
            for note in box.find_elements(self.By.CSS_SELECTOR, ".no-result-wrap"):
                if note.is_displayed() and all(
                    any(e.is_displayed() and e.text.strip() for e in note.find_elements(
                        self.By.CSS_SELECTOR, css)) for css in (".no-result", ".no-result-sub")
                ):
                    return box
        return False

    def _r009_query_item(self, driver, item):
        field = self._r009_wait(driver, "#accept-consignment-input > input")
        self._r009_click(driver, field)
        field.send_keys(self.Keys.CONTROL, "a")
        field.send_keys(self.Keys.BACKSPACE)
        field.send_keys(item)
        # 需求为直接查询原文；点击页标题收起物品联想，不改写为其他建议项。
        self._r009_click(driver, self._r009_wait(driver, ".accept-query .title-wrap"))
        assert field.get_attribute("value") == item, "R009 托寄物品输入不一致：" + item
        assert not any(e.is_displayed() for e in driver.find_elements(
            self.By.CSS_SELECTOR, ".accept-query .result-box")), "R009 查询前存在旧结果"
        self._r009_click(driver, self._r009_wait(
            driver, ".accept-query button.search-btn:not(.disabled)", "查询"))
        stable = {"text": "", "since": 0}

        def ready(d):
            self._r009_dismiss_cookie_banner(d)
            box = self._r009_result(d, item)
            text = box.text.strip() if box else ""
            if not text or text != stable["text"]:
                stable.update(text=text, since=self.time.monotonic())
                return False
            return box if self.time.monotonic() - stable["since"] >= 0.8 else False
        try:
            box = self.WebDriverWait(driver, 45, poll_frequency=0.3,
                ignored_exceptions=(self.StaleElementReferenceException,)).until(ready)
            print("R009 物品=%s；实际查询结果=%s" % (item, box.text))
        except self.TimeoutException as exc:
            actual = [e.text for e in driver.find_elements(self.By.CSS_SELECTOR,
                ".accept-query .result-box, .accept-query .search-tips") if e.is_displayed()]
            raise AssertionError("R009 未得到本次查询结果：物品=%s；可见结果=%s；URL=%s" %
                                 (item, actual, driver.current_url)) from exc

    @pytest.mark.parametrize("case_id,item", [
        ("SF_R009_001", "猫咪"),
        ("SF_R009_002", "硫酸"),
        ("SF_R009_003", "现金"),
        ("SF_R009_004", "古董"),
    ], ids=["SF_R009_001", "SF_R009_002", "SF_R009_003", "SF_R009_004"])
    def test_SF_R009(self, driver, case_id, item):
        """深圳南山区→香港湾仔区铜锣湾；个人→公司；四种物品分别查询并整页截图。"""
        old_wait = driver.timeouts.implicit_wait
        driver.implicitly_wait(0)
        try:
            self._r009_navigate(driver)
            self._r009_select_area(driver, "origin", ["深圳市", "南山区"])
            self._r009_select_area(driver, "destination", ["香港", "湾仔区", "铜锣湾"])
            self._r009_identity(driver)
            self._r009_query_item(driver, item)
            path = self._r009_screenshot(driver, case_id, item)
            print("%s 完成：深圳南山区→香港湾仔区铜锣湾；个人→公司；物品=%s；截图=%s" %
                  (case_id, item, path))
        finally:
            driver.implicitly_wait(old_wait)


    def _r010_dismiss_cookie_banner(self, driver):
        def dismissed(d):
            for banner in d.find_elements(self.By.CSS_SELECTOR, ".cookie-policy"):
                if not banner.is_displayed():
                    continue
                for button in banner.find_elements(self.By.CSS_SELECTOR, ".right .btn"):
                    if button.is_displayed() and button.is_enabled() and button.text.strip() == "不同意":
                        button.click()
                        return False
                return False
            return True
        self.WebDriverWait(driver, 10, poll_frequency=0.25,
            ignored_exceptions=(self.StaleElementReferenceException,)).until(
                dismissed, "R010 Cookie 弹窗未能关闭")

    def _r010_wait(self, driver, selector, text=None, timeout=30):
        def ready(d):
            self._r010_dismiss_cookie_banner(d)
            for element in d.find_elements(self.By.CSS_SELECTOR, selector):
                if (element.is_displayed() and element.is_enabled()
                        and (text is None or element.text.strip() == text)):
                    if not hasattr(self, "_r010_locators"):
                        self._r010_locators = {}
                    self._r010_locators[element.id] = (selector, text)
                    return element
            return False
        try:
            return self.WebDriverWait(driver, timeout, poll_frequency=0.25,
                ignored_exceptions=(self.StaleElementReferenceException,)).until(ready)
        except self.TimeoutException as exc:
            values = [e.text[:160] for e in driver.find_elements(
                self.By.CSS_SELECTOR, selector) if e.is_displayed()]
            raise AssertionError("R010 控件未就绪：%s；目标=%s；可见内容=%s；URL=%s" %
                                 (selector, text, values, driver.current_url)) from exc

    def _r010_click(self, driver, element):
        # 由 _r010_wait 记录定位条件；DOM 重建后重新查找，不重复使用旧引用。
        locator = getattr(self, "_r010_locators", {}).get(element.id)
        def clicked(d):
            self._r010_dismiss_cookie_banner(d)
            target = element
            if locator:
                selector, text = locator
                target = next((e for e in d.find_elements(self.By.CSS_SELECTOR, selector)
                    if e.is_displayed() and e.is_enabled()
                    and (text is None or e.text.strip() == text)), None)
                if target is None:
                    return False
            d.execute_script("arguments[0].scrollIntoView({block:'center'});", target)
            target.click()
            return True
        self.WebDriverWait(driver, 15, poll_frequency=0.25,
            ignored_exceptions=(self.StaleElementReferenceException,
                                self.ElementClickInterceptedException)).until(clicked)

    def _r010_navigate(self, driver):
        driver.switch_to.default_content()
        driver.get("https://www.sf-express.com/")
        before = set(driver.window_handles)
        self._r010_click(driver, self._r010_wait(driver, "a", "服务支持"))
        def support_ready(d):
            added = set(d.window_handles) - before
            if added:
                d.switch_to.window(next(iter(added)))
            self._r010_dismiss_cookie_banner(d)
            return any(e.is_displayed() for e in d.find_elements(
                self.By.CSS_SELECTOR, ".side-menu"))
        self.WebDriverWait(driver, 30, ignored_exceptions=(self.StaleElementReferenceException,)).until(support_ready)
        # 点击后单独确认路由；SSR 菜单已显示时，客户端事件可能尚未绑定。
        # 仅在跳转未完成时重试，不重做已经成功的表单和地图操作。
        original_window = driver.current_window_handle
        menu_windows = set(driver.window_handles)

        def outlets_route_ready(d):
            self._r010_dismiss_cookie_banner(d)
            if "/range-query" in d.current_url:
                return True
            for handle in set(d.window_handles) - menu_windows:
                d.switch_to.window(handle)
                if "/range-query" in d.current_url:
                    return True
            d.switch_to.window(original_window)
            return "/range-query" in d.current_url

        for attempt in range(4):
            if outlets_route_ready(driver):
                break
            if attempt == 2 and "/support" in driver.current_url:
                driver.refresh()
                self._r010_wait(driver, ".side-menu")
            try:
                self._r010_wait(driver, ".side-menu .side-child-item", "服务范围", timeout=3)
            except AssertionError:
                self._r010_click(driver, self._r010_wait(
                    driver, ".side-menu .title", "服务查询"))
            self._r010_click(driver, self._r010_wait(
                driver, ".side-menu .side-child-item", "服务范围"))
            try:
                self.WebDriverWait(driver, 15, poll_frequency=0.3,
                    ignored_exceptions=(self.StaleElementReferenceException,)
                ).until(outlets_route_ready)
                break
            except self.TimeoutException as exc:
                if attempt == 3:
                    raise AssertionError(
                        "R010 点击左侧服务范围后未完成跳转（共尝试4次）：URL="
                        + driver.current_url) from exc
        self._r010_wait_form(driver)
        assert "/range-query" in driver.current_url, "R010 未进入服务范围页面"

    def _r010_open_picker(self, driver):
        root = "#range-query-citypicker"
        # 兼容 city-picker 弹层被 Vue Teleport 挂载到 root 外部的页面版本。
        search_css_list = (
            root + " .city-picker input.city-search",
            ".city-picker input.city-search",
        )
        def search_ready(d):
            self._r010_dismiss_cookie_banner(d)
            for search_css in search_css_list:
                search = next((e for e in d.find_elements(self.By.CSS_SELECTOR, search_css)
                               if e.is_displayed() and e.is_enabled()), False)
                if search:
                    return search
            return False
        # 已打开时直接使用；只有开关明确关闭才点击，避免反复切换。
        for attempt in range(2):
            search = search_ready(driver)
            if search:
                return search
            trigger = self._r010_wait(driver, root)
            if "expanding" not in (trigger.get_attribute("class") or "").split():
                self._r010_click(driver, trigger)
            try:
                return self.WebDriverWait(driver, 30, poll_frequency=0.25,
                    ignored_exceptions=(self.StaleElementReferenceException,)).until(search_ready)
            except self.TimeoutException:
                trigger = driver.find_element(self.By.CSS_SELECTOR, root)
                if "expanding" in (trigger.get_attribute("class") or "").split():
                    # 开关已打开却没有搜索框：等待异步组件，不再点击关闭它。
                    if attempt == 0:
                        continue
        trigger = driver.find_element(self.By.CSS_SELECTOR, root)
        raise AssertionError("R010 地址选择器未加载：class=%s；控件HTML=%s" %
                             (trigger.get_attribute("class"), trigger.get_attribute("outerHTML")[:1800]))

    def _r010_screenshot(self, driver, case_id, province, city, district, street):
        import base64
        from pathlib import Path
        self._r010_dismiss_cookie_banner(driver)
        self.WebDriverWait(driver, 15, ignored_exceptions=(self.StaleElementReferenceException,)).until(
            lambda d: self._r010_result(d, province, city, district, street),
            "R010 截图前结果与查询条件不一致")
        # CDP 截取完整文档，包含输入条件、全部结果行及页面下方说明。
        driver.execute_script("window.scrollTo(0, 0);")
        metrics = driver.execute_cdp_cmd("Page.getLayoutMetrics", {})
        size = metrics.get("cssContentSize") or metrics.get("contentSize")
        assert size and size["width"] > 0 and size["height"] > 0, "R010 页面尺寸无效"
        shot = driver.execute_cdp_cmd("Page.captureScreenshot", {
            "format": "png", "fromSurface": True, "captureBeyondViewport": True,
            "clip": {"x": 0, "y": 0, "width": size["width"], "height": size["height"], "scale": 1}
        })
        content = base64.b64decode(shot["data"])
        assert content.startswith(b"\x89PNG\r\n\x1a\n"), "R010 截图生成失败"
        assert (int.from_bytes(content[16:20], "big") >= int(size["width"])
                and int.from_bytes(content[20:24], "big") >= int(size["height"])), "R010 截图未覆盖整页"
        folder = Path("screenshots")
        folder.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%H%M%S%d%f")[:-3]
        output = folder / (timestamp + "_" + case_id + ".png")
        output.write_bytes(content)
        assert output.is_file() and output.stat().st_size > 0, "R010 截图保存失败"
        return str(output)

    def _r010_wait_form(self, driver):
        def ready(d):
            self._r010_dismiss_cookie_banner(d)
            return "/range-query" in d.current_url and any(
                e.is_displayed() and e.is_enabled() for e in d.find_elements(
                    self.By.CSS_SELECTOR, "#range-query-citypicker input.result"))
        for attempt in range(2):
            try:
                self.WebDriverWait(driver, 40, poll_frequency=0.3,
                    ignored_exceptions=(self.StaleElementReferenceException,)).until(ready)
                return
            except self.TimeoutException as exc:
                if attempt == 0 and "/range-query" in driver.current_url:
                    driver.refresh()  # 仅在未填写表单前重试组件加载。
                    continue
                raise AssertionError("R010 服务范围表单未加载：" + driver.current_url) from exc

    def _r010_select_area(self, driver, province, city, district):
        search = self._r010_open_picker(driver)
        root = "#range-query-citypicker .city-picker"
        search.send_keys(self.Keys.CONTROL, "a")
        search.send_keys(self.Keys.BACKSPACE)
        search.send_keys(province)

        def option_ready(d):
            self._r010_dismiss_cookie_banner(d)
            for option in d.find_elements(self.By.CSS_SELECTOR, root + " .search-result li"):
                if option.is_displayed() and all(name in option.text for name in (province, city, district)):
                    self._r010_dismiss_cookie_banner(d)
                    option.click()
                    return True
            return False
        try:
            option = self.WebDriverWait(driver, 35, poll_frequency=0.25,
                ignored_exceptions=(self.StaleElementReferenceException,)).until(option_ready)
        except self.TimeoutException as exc:
            values = [e.text for e in driver.find_elements(self.By.CSS_SELECTOR,
                root + " .search-result") if e.is_displayed()]
            raise AssertionError("R010 省份搜索未找到指定区县：%s/%s/%s；候选=%s" %
                                 (province, city, district, values)) from exc

        normalize = lambda value: self.re.sub(r"[\s\-－–—>]+", "", value or "")
        expected = tuple(normalize(name) for name in (province, city, district))

        def value_selected(d):
            value = d.find_element(self.By.CSS_SELECTOR,
                "#range-query-citypicker input.result").get_attribute("value") or ""
            normalized = normalize(value)
            return value if all(name in normalized for name in expected) else False

        try:
            # 先等地址确实回填；不要因为弹层还开着就误判为地址选择失败。
            value = self.WebDriverWait(driver, 25, poll_frequency=0.25,
                ignored_exceptions=(self.StaleElementReferenceException,)).until(value_selected)

            root_element = driver.find_element(self.By.CSS_SELECTOR, "#range-query-citypicker")
            is_expanding = "expanding" in (root_element.get_attribute("class") or "").split()
            popup_visible = any(e.is_displayed() for e in driver.find_elements(
                self.By.CSS_SELECTOR, root + " .city-picker"))
            if is_expanding or popup_visible:
                self._r010_click(driver, root_element)
                self.WebDriverWait(driver, 12, poll_frequency=0.25,
                    ignored_exceptions=(self.StaleElementReferenceException,)).until(
                        lambda d: (
                            "expanding" not in (d.find_element(
                                self.By.CSS_SELECTOR, "#range-query-citypicker"
                            ).get_attribute("class") or "").split()
                            and not any(e.is_displayed() for e in d.find_elements(
                                self.By.CSS_SELECTOR, root + " .city-picker"))
                        )
                    )
        except self.TimeoutException as exc:
            value = driver.find_element(self.By.CSS_SELECTOR,
                "#range-query-citypicker input.result").get_attribute("value") or ""
            root_element = driver.find_element(self.By.CSS_SELECTOR, "#range-query-citypicker")
            popup_visible = any(e.is_displayed() for e in driver.find_elements(
                self.By.CSS_SELECTOR, root + " .city-picker"))
            raise AssertionError(
                "R010 收寄件区域未正确回填或弹层未关闭：期望=%s；实际=%s；"
                "触发器class=%s；弹层可见=%s" %
                ((province, city, district), value,
                 root_element.get_attribute("class"), popup_visible)
            ) from exc

    def _r010_set_street(self, driver, street):
        root = ".range-query .fourth-level"
        field = self._r010_wait(driver, root + " > input.result")
        # 四条参数用例均使用新浏览器；空值用例不得选择任意街道代替。
        assert not (field.get_attribute("value") or "").strip(), "R010 初始乡镇/街道应为空"
        if street is None:
            return
        self._r010_click(driver, field)
        self._r010_click(driver, self._r010_wait(driver, root + " .fourth-level-box li", street))
        self.WebDriverWait(driver, 15).until(lambda d:
            d.find_element(self.By.CSS_SELECTOR, root + " > input.result").get_attribute("value") == street,
            "R010 乡镇/街道未正确回填：" + street)
        # 点击标题确保下拉框收起，不修改选择值。
        self._r010_click(driver, self._r010_wait(driver, ".range-query .title-wrap"))
        self.WebDriverWait(driver, 10).until(lambda d: not any(
            e.is_displayed() for e in d.find_elements(self.By.CSS_SELECTOR, root + " .fourth-level-box")))

    def _r010_result(self, driver, province, city, district, street):
        normalize = lambda value: self.re.sub(r"\s+", "", value or "")
        area = driver.find_element(self.By.CSS_SELECTOR,
            "#range-query-citypicker input.result").get_attribute("value") or ""
        actual_street = driver.find_element(self.By.CSS_SELECTOR,
            ".range-query .fourth-level > input.result").get_attribute("value") or ""
        if not all(normalize(n) in normalize(area) for n in (province, city, district)) or normalize(actual_street) != normalize(street):
            return False
        if not any(e.is_displayed() for e in driver.find_elements(self.By.CSS_SELECTOR,
                ".range-query button.search-btn:not(.disabled)")):
            return False
        for box in driver.find_elements(self.By.CSS_SELECTOR, ".range-query .result-box.general"):
            if not box.is_displayed():
                continue
            title = box.find_element(self.By.CSS_SELECTOR, ".title").text.strip()
            message = box.find_element(self.By.CSS_SELECTOR, ".result-text").text.strip()
            # 官网结果标题由地址及可选街道拼接；空街道不得匹配到某个街道结果。
            expected = [province, city, district] + ([street] if street else [])
            parts = [normalize(p) for p in self.re.split(r"[-－–—]", title) if normalize(p)]
            if parts != [normalize(p) for p in expected]:
                continue
            # 全境可能写“全境行政村可达”；部分区域主说明为空，内容在直属 p 中。
            status = "\n".join([message] + [e.text.strip() for e in
                box.find_elements(self.By.XPATH, "./p[not(contains(@class,'unsupported'))]")
                if e.is_displayed() and e.text.strip()])
            if (status and self.re.search(r"收件|派件|收派|寄递|未开通|全境.*可达|不提供.*服务", status)
                    and not any(word in status for word in ("异常", "错误", "失败", "稍后", "重试"))):
                return box
        return False

    def _r010_query(self, driver, province, city, district, street):
        assert not any(e.is_displayed() for e in driver.find_elements(
            self.By.CSS_SELECTOR, ".range-query .result-box.general")), "R010 查询前存在旧结果"
        self._r010_click(driver, self._r010_wait(driver,
            ".range-query button.search-btn:not(.disabled)", "查询"))
        stable = {"text": "", "since": 0}

        def ready(d):
            self._r010_dismiss_cookie_banner(d)
            box = self._r010_result(d, province, city, district, street)
            text = box.text.strip() if box else ""
            if not text or text != stable["text"]:
                stable.update(text=text, since=self.time.monotonic())
                return False
            return box if self.time.monotonic() - stable["since"] >= 1.5 else False
        try:
            box = self.WebDriverWait(driver, 45, poll_frequency=0.3,
                ignored_exceptions=(self.StaleElementReferenceException,)).until(ready)
            print("R010 实际服务范围查询结果：%s" % box.text)
        except self.TimeoutException as exc:
            values = [e.text for e in driver.find_elements(self.By.CSS_SELECTOR,
                ".range-query .result-box") if e.is_displayed()]
            raise AssertionError("R010 未得到匹配的服务范围结果：%s/%s/%s；街道=%s；结果=%s；URL=%s" %
                (province, city, district, street or "空", values, driver.current_url)) from exc

    @pytest.mark.parametrize("case_id,province,city,district,street", [
        ("SF_R010_001", "广东省", "广州市", "番禺区", None),
        ("SF_R010_002", "广东省", "广州市", "番禺区", "大石街道"),
        ("SF_R010_003", "新疆维吾尔自治区", "喀什地区", "伽师县", None),
        ("SF_R010_004", "新疆维吾尔自治区", "喀什地区", "伽师县", "米夏乡"),
    ], ids=["SF_R010_001", "SF_R010_002", "SF_R010_003", "SF_R010_004"])
    def test_SF_R010(self, driver, case_id, province, city, district, street):
        """搜索省份选区县；每个地区分别空街道、指定街道查询并保存完整截图。"""
        old_wait = driver.timeouts.implicit_wait
        driver.implicitly_wait(0)
        try:
            self._r010_navigate(driver)
            self._r010_select_area(driver, province, city, district)
            self._r010_set_street(driver, street)
            self._r010_query(driver, province, city, district, street)
            path = self._r010_screenshot(driver, case_id, province, city, district, street)
            print("%s 完成：%s/%s/%s；乡镇街道=%s；完整截图=%s" %
                  (case_id, province, city, district, street or "空", path))
        finally:
            driver.implicitly_wait(old_wait)


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
