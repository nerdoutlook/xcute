import '../styles/globals.css'; // Correct path
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import SocketProvider from '../components/SocketProvider';

function MyApp({ Component, pageProps }) {
  return (
    <SocketProvider>
      <Component {...pageProps} />
      <ToastContainer position="top-right" autoClose={5000} />
    </SocketProvider>
  );
}

export default MyApp;
