import objc
from Cocoa import (
    NSWindow, NSColor, NSScreen, NSView, NSBezierPath,
    NSBackingStoreBuffered, NSFloatingWindowLevel, NSMakeRect,
)

DOT_RADIUS = 18


class DotView(NSView):
    def initWithFrame_(self, frame):
        self = objc.super(DotView, self).initWithFrame_(frame)
        if self is None:
            return None
        self.point = (0.0, 0.0)
        self.confirmed = False
        return self

    def isFlipped(self):
        return True

    def drawRect_(self, rect):
        NSColor.clearColor().set()
        NSBezierPath.fillRect_(rect)
        color = NSColor.greenColor() if self.confirmed else NSColor.orangeColor()
        color.set()
        x, y = self.point
        oval = NSMakeRect(x - DOT_RADIUS, y - DOT_RADIUS, DOT_RADIUS * 2, DOT_RADIUS * 2)
        NSBezierPath.bezierPathWithOvalInRect_(oval).fill()


class GazeOverlay:
    def __init__(self):
        screen_frame = NSScreen.mainScreen().frame()
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            screen_frame, 0, NSBackingStoreBuffered, False
        )
        self.window.setOpaque_(False)
        self.window.setBackgroundColor_(NSColor.clearColor())
        self.window.setLevel_(NSFloatingWindowLevel)
        self.window.setIgnoresMouseEvents_(True)
        self.window.setHasShadow_(False)
        self.window.setCollectionBehavior_(1 << 0 | 1 << 8)

        self.view = DotView.alloc().initWithFrame_(screen_frame)
        self.window.setContentView_(self.view)

    def show(self):
        self.window.makeKeyAndOrderFront_(None)
        self.window.orderFrontRegardless()

    def hide(self):
        self.window.orderOut_(None)

    def update(self, point, confirmed):
        self.view.point = point
        self.view.confirmed = confirmed
        self.view.setNeedsDisplay_(True)
        self.window.displayIfNeeded()
