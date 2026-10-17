import './fonts.css';
import './styles.css';

// Paint the prerendered page before loading its interactive enhancements.
requestAnimationFrame(() => requestAnimationFrame(() => { void import('./hydrate'); }));
