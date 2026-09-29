import assert from 'node:assert/strict';
import test from 'node:test';
import { JSDOM } from 'jsdom';
import { installCanvasBackingStore } from './canvas-lifecycle.ts';

test('canvas lifecycle preserves HiDPI/aspect/fullscreen sizing and ignores callbacks after disposal', t => {
    const dom = new JSDOM('<canvas></canvas>');
    t.after(() => dom.window.close());
    const canvas = dom.window.document.querySelector('canvas')!;
    canvas.getBoundingClientRect = () => ({ width: 800, height: 600 }) as DOMRect;
    let viewport = { innerWidth: 1200, innerHeight: 900, fullscreen: false, devicePixelRatio: 2 };
    let subscribed!: () => void, disposals = 0;
    const lifecycle = installCanvasBackingStore(canvas, {
        viewport: () => viewport,
        subscribe: sync => { subscribed = sync; return () => { disposals++; }; },
    });
    assert.equal(canvas.width, 1600); assert.equal(canvas.height, 1200);
    assert.equal(canvas.style.width, '1184px'); assert.equal(canvas.style.height, '884px');
    viewport = { innerWidth: 1600, innerHeight: 900, fullscreen: true, devicePixelRatio: 1 };
    subscribed();
    assert.equal(canvas.style.width, '1600px'); assert.equal(canvas.style.height, '900px');
    assert.equal(canvas.width, 800);
    lifecycle.dispose(); lifecycle.dispose();
    assert.equal(disposals, 1);
    viewport = { ...viewport, devicePixelRatio: 3 };
    subscribed(); lifecycle.sync();
    assert.equal(canvas.width, 800);
});

test('browser resize delivery defers layout writes and cancels queued work on disposal', t => {
    const dom = new JSDOM('<canvas></canvas>');
    const previous = ['window', 'document', 'ResizeObserver'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)] as const);
    t.after(() => {
        for (const [key, descriptor] of previous) {
            if (descriptor) Object.defineProperty(globalThis, key, descriptor);
            else Reflect.deleteProperty(globalThis, key);
        }
        dom.window.close();
    });
    let notify!: () => void;
    let pending: FrameRequestCallback | undefined;
    let scheduled = 0;
    Object.defineProperty(globalThis, 'window', { configurable: true, value: dom.window });
    Object.defineProperty(globalThis, 'document', { configurable: true, value: dom.window.document });
    Object.defineProperty(globalThis, 'ResizeObserver', { configurable: true, value: class {
        constructor(callback: () => void) { notify = callback; }
        observe() {}
        disconnect() {}
    } });
    dom.window.requestAnimationFrame = callback => { pending = callback; return ++scheduled; };
    dom.window.cancelAnimationFrame = () => { pending = undefined; };
    const canvas = dom.window.document.querySelector('canvas')!;
    let measuredWidth = 800;
    canvas.getBoundingClientRect = () => ({ width: measuredWidth, height: 600 }) as DOMRect;
    const lifecycle = installCanvasBackingStore(canvas);
    assert.equal(canvas.width, 800);
    measuredWidth = 900;
    notify(); notify();
    assert.equal(canvas.width, 800, 'observer delivery must not synchronously change layout');
    assert.equal(scheduled, 1);
    pending!(0);
    assert.equal(canvas.width, 900);
    notify();
    lifecycle.dispose();
    assert.equal(pending, undefined);
});
