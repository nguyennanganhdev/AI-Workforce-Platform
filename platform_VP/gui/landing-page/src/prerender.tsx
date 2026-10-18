import { renderToString } from 'react-dom/server';
import App from './App';
import { MotionProvider } from '../lib/motion';

export function render() {
  return renderToString(<MotionProvider><App /></MotionProvider>);
}
