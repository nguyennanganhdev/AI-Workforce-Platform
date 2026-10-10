/** Test-only DOM setup; production uses the browser and shared transport. */
import { JSDOM } from 'jsdom';
import * as React from 'react';

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost' });
Object.assign(globalThis, {
	window: dom.window, document: dom.window.document,
	HTMLElement: dom.window.HTMLElement, Node: dom.window.Node,
	MutationObserver: dom.window.MutationObserver,
	IS_REACT_ACT_ENVIRONMENT: true,
	React,
});
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true });
