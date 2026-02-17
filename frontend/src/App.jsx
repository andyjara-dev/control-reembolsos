import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Pagos from './pages/Pagos';
import { AppBar, Toolbar, Typography, Button, Box, Container } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';

function PrivateRoute({ children }) {
  const { isAuth } = useAuth();
  return isAuth ? children : <Navigate to="/login" />;
}

function Layout() {
  const { logout } = useAuth();
  return (
    <>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            Control de Reembolsos
          </Typography>
          <Button color="inherit" component={RouterLink} to="/">Dashboard</Button>
          <Button color="inherit" component={RouterLink} to="/pagos">Pagos</Button>
          <Button color="inherit" onClick={logout}>Salir</Button>
        </Toolbar>
      </AppBar>
      <Container maxWidth="lg" sx={{ mt: 3, mb: 3 }}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/pagos" element={<Pagos />} />
        </Routes>
      </Container>
    </>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/*" element={<PrivateRoute><Layout /></PrivateRoute>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
