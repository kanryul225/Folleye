import pathlib
import objc
from Cocoa import (
    NSWindow, NSView, NSTextField, NSButton, NSColor, NSFont,
    NSScreen, NSBackingStoreBuffered, NSMakeRect,
    NSTextAlignmentCenter, NSTextAlignmentLeft,
    NSObject, NSImage, NSImageView,
)

W = 520
H_WELCOME = 520
H_PREP    = 560
H_DONE    = 460

_IMAGE_DIR = pathlib.Path(__file__).parent.parent / "image"

_refs = []


# ── 뷰 헬퍼 ──────────────────────────────────────────────────────────

def _label(text, x, y, w, h, size=13, bold=False,
           align=NSTextAlignmentLeft, color=None):
    f = NSTextField.alloc().initWithFrame_(NSMakeRect(x, y, w, h))
    f.setStringValue_(text)
    f.setBezeled_(False)
    f.setDrawsBackground_(False)
    f.setEditable_(False)
    f.setSelectable_(False)
    f.setFont_(NSFont.boldSystemFontOfSize_(size) if bold
               else NSFont.systemFontOfSize_(size))
    f.setAlignment_(align)
    f.cell().setWraps_(True)          # 자동 줄바꿈
    f.cell().setLineBreakMode_(0)     # NSLineBreakByWordWrapping
    if color:
        f.setTextColor_(color)
    return f


def _image_view(filename, x, y, w, h):
    img = NSImage.alloc().initWithContentsOfFile_(str(_IMAGE_DIR / filename))
    view = NSImageView.alloc().initWithFrame_(NSMakeRect(x, y, w, h))
    view.setImage_(img)
    view.setImageScaling_(3)  # NSImageScaleProportionallyUpOrDown
    return view


def _sep(y):
    v = NSView.alloc().initWithFrame_(NSMakeRect(40, y, W - 80, 1))
    v.setWantsLayer_(True)
    v.layer().setBackgroundColor_(NSColor.separatorColor().CGColor())
    return v


def _centered_buttons(specs, y, gap=16, target=None):
    total = sum(w for _, w, _ in specs) + gap * (len(specs) - 1)
    x = int((W - total) / 2)
    out = []
    for title, bw, sel in specs:
        b = NSButton.alloc().initWithFrame_(NSMakeRect(x, y, bw, 32))
        b.setTitle_(title)
        b.setBezelStyle_(1)
        b.setTarget_(target)
        b.setAction_(sel)
        out.append(b)
        x += bw + gap
    return out


# ── Delegate ──────────────────────────────────────────────────────────

class _Delegate(NSObject):
    def init(self):
        self = objc.super(_Delegate, self).init()
        if self is None:
            return None
        self.owner = None
        return self

    def goToCalibPrep_(self, _):  self.owner.show_calib_prep()
    def goToWelcome_(self, _):    self.owner._show_welcome()
    def beginCalib_(self, _):     self.owner._run_calibration()
    def restartCalib_(self, _):   self.owner.show_calib_prep()
    def startTracking_(self, _):  self.owner._run_start_tracking()
    def closeWin_(self, _):       self.owner._close()


# ── 창 클래스 ─────────────────────────────────────────────────────────

class OnboardingWindow:
    def __init__(self, on_calibrate=None, on_start_tracking=None):
        self._on_calibrate = on_calibrate
        self._on_start_tracking = on_start_tracking

        self._win = self._make_win(H_WELCOME)
        self._dlg = _Delegate.alloc().init()
        self._dlg.owner = self
        _refs.extend([self._win, self._dlg])

        self._show_welcome()

    def _make_win(self, h):
        screen = NSScreen.mainScreen().frame()
        sx = screen.origin.x + (screen.size.width  - W) / 2
        sy = screen.origin.y + (screen.size.height - h) / 2
        win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(sx, sy, W, h), 1 | 2, NSBackingStoreBuffered, False
        )
        win.setTitle_("Folleye")
        win.setReleasedWhenClosed_(False)
        return win

    def _resize(self, new_h):
        screen = NSScreen.mainScreen().frame()
        sx = screen.origin.x + (screen.size.width  - W) / 2
        sy = screen.origin.y + (screen.size.height - new_h) / 2
        frame = self._win.frameRectForContentRect_(NSMakeRect(sx, sy, W, new_h))
        self._win.setFrame_display_(frame, False)

    def _clear(self):
        for v in list(self._win.contentView().subviews()):
            v.removeFromSuperview()

    def _show(self):
        self._win.makeKeyAndOrderFront_(None)
        self._win.orderFrontRegardless()

    # ── Screen 1 : Welcome (H=520) ────────────────────────────────────

    def _show_welcome(self):
        self._resize(H_WELCOME)
        self._clear()
        c, g, P = self._win.contentView(), NSColor.secondaryLabelColor(), 44

        # logo_right.png: w=253 h=77, 수평 중앙, 28px top padding
        c.addSubview_(_image_view("logo_right.png", 133, 415, 253, 77))

        c.addSubview_(_label(
            "Folleye detects where your eyes are looking and automatically moves your mouse cursor to that window — so you can scroll without touching your mouse.",
            P, 327, W-P*2, 72, size=13, align=NSTextAlignmentCenter, color=g,
        ))
        c.addSubview_(_sep(311))

        c.addSubview_(_label("STEP 1 — Calibration", P, 275, W-P*2, 22, size=13, bold=True))
        c.addSubview_(_label(
            "Only needed once. Follow the dots on screen with your eyes and Folleye will learn your gaze pattern. (~30 seconds)",
            P, 225, W-P*2, 44, size=12, color=g,
        ))

        c.addSubview_(_label("STEP 2 — Start Tracking", P, 189, W-P*2, 22, size=13, bold=True))
        c.addSubview_(_label(
            "After calibration, click 'Start Tracking'. Folleye moves your cursor to the window you're looking at whenever your mouse is idle — it won't interfere with normal mouse use.\n\n💡 Tip: enable 'Show Gaze Dot' in the menu to visualize where Folleye thinks you're looking (off by default).",
            P, 83, W-P*2, 100, size=12, color=g,
        ))

        for b in _centered_buttons([
            ("Start Calibration", 160, "goToCalibPrep:"),
            ("Later", 90, "closeWin:"),
        ], y=28, target=self._dlg):
            c.addSubview_(b)

        self._show()

    # ── Screen 2 : Calibration Prep (H=560) ──────────────────────────

    def show_calib_prep(self):
        self._resize(H_PREP)
        self._clear()
        c, g, P = self._win.contentView(), NSColor.secondaryLabelColor(), 44

        c.addSubview_(_label("Before You Start", 0, 500, W, 44,
                             size=22, bold=True, align=NSTextAlignmentCenter))
        c.addSubview_(_label(
            "Follow these tips for the best calibration results.",
            0, 462, W, 24, size=13, align=NSTextAlignmentCenter, color=g,
        ))
        c.addSubview_(_sep(446))

        tips = [
            (406, "💺  Sit comfortably",
             358, "Stay in a natural, stable posture throughout the session. Avoid leaning forward or tilting your head."),
            (318, "👀  Eyes only",
             270, "Move only your eyes to follow each dot — not your head. Keep your face pointed toward the screen."),
            (230, "🟢  Wait for green",
             182, "Each dot starts red and turns green when your gaze is recorded. Stay focused on the dot until it changes color."),
            (142, "🔁  Recalibrate anytime",
              94, "If tracking drifts later, redo calibration from the menu bar icon — it takes about 30 seconds."),
        ]
        for ty, tt, dy, dt in tips:
            c.addSubview_(_label(tt, P, ty, W-P*2, 22, size=13, bold=True))
            c.addSubview_(_label(dt, P, dy, W-P*2, 40, size=12, color=g))

        for b in _centered_buttons([
            ("Begin Calibration", 160, "beginCalib:"),
            ("Back", 80, "goToWelcome:"),
        ], y=32, target=self._dlg):
            c.addSubview_(b)

        self._show()

    # ── Screen 3 : Complete (H=460) ───────────────────────────────────

    def show_complete(self):
        self._resize(H_DONE)
        self._clear()
        c, g, P = self._win.contentView(), NSColor.secondaryLabelColor(), 44

        c.addSubview_(_label("Calibration Complete  ✅", 0, 368, W, 44,
                             size=22, bold=True, align=NSTextAlignmentCenter))
        c.addSubview_(_label(
            "Your gaze pattern has been learned successfully. You're ready to start tracking.",
            P, 298, W-P*2, 56, size=14, align=NSTextAlignmentCenter, color=g,
        ))
        c.addSubview_(_sep(280))

        c.addSubview_(_label("How tracking works", 0, 244, W, 22,
                             size=13, bold=True, align=NSTextAlignmentCenter))
        c.addSubview_(_label(
            "Folleye moves your cursor to the window you're looking at, but only when your mouse has been idle for ~1.5 seconds — so it never interrupts normal mouse use. Toggle tracking anytime via menu.\n\nTry to keep a similar posture to when you calibrated. If tracking feels off, click Calibration in the menu bar to redo it.",
            P, 120, W-P*2, 116, size=12, align=NSTextAlignmentCenter, color=g,
        ))

        for b in _centered_buttons([
            ("Start Tracking", 140, "startTracking:"),
            ("Recalibrate", 110, "restartCalib:"),
        ], y=60, target=self._dlg):
            c.addSubview_(b)

        self._show()

    # ── 액션 ──────────────────────────────────────────────────────────

    def _run_calibration(self):
        self._win.orderOut_(None)
        if self._on_calibrate:
            self._on_calibrate()
        self.show_complete()

    def _run_start_tracking(self):
        self._win.orderOut_(None)
        if self._on_start_tracking:
            self._on_start_tracking()

    def _close(self):
        self._win.orderOut_(None)


def show_onboarding(on_calibrate=None, on_start_tracking=None):
    return OnboardingWindow(on_calibrate=on_calibrate, on_start_tracking=on_start_tracking)
