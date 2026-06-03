import { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Pagos from './pages/Pagos';
import Ajustes from './pages/Ajustes';
import {
  AppBar, Toolbar, Button, Box, Container,
  Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, Stack, Alert,
} from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import api from './api';

function CambiarPasswordModal({ open, onClose }) {
  const [form, setForm] = useState({ actual: '', nueva: '', confirmar: '' });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleClose = () => {
    setForm({ actual: '', nueva: '', confirmar: '' });
    setError('');
    setSuccess('');
    onClose();
  };

  const handleSubmit = async () => {
    setError('');
    setSuccess('');
    if (form.nueva !== form.confirmar) {
      setError('La nueva contraseña y la confirmación no coinciden');
      return;
    }
    if (!form.nueva) {
      setError('La nueva contraseña no puede estar vacía');
      return;
    }
    try {
      await api.put('/auth/cambiar-password', {
        password_actual: form.actual,
        password_nuevo: form.nueva,
      });
      setSuccess('Contraseña actualizada correctamente');
      setForm({ actual: '', nueva: '', confirmar: '' });
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al cambiar la contraseña');
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="xs" fullWidth>
      <DialogTitle>Cambiar Contraseña</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {error && <Alert severity="error">{error}</Alert>}
          {success && <Alert severity="success">{success}</Alert>}
          <TextField
            label="Contraseña actual"
            type="password"
            value={form.actual}
            onChange={(e) => setForm({ ...form, actual: e.target.value })}
            fullWidth
          />
          <TextField
            label="Nueva contraseña"
            type="password"
            value={form.nueva}
            onChange={(e) => setForm({ ...form, nueva: e.target.value })}
            fullWidth
          />
          <TextField
            label="Confirmar nueva contraseña"
            type="password"
            value={form.confirmar}
            onChange={(e) => setForm({ ...form, confirmar: e.target.value })}
            fullWidth
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Cancelar</Button>
        <Button variant="contained" onClick={handleSubmit}>Cambiar</Button>
      </DialogActions>
    </Dialog>
  );
}

function PrivateRoute({ children }) {
  const { isAuth } = useAuth();
  return isAuth ? children : <Navigate to="/login" />;
}

function AppLogo() {
  return (
    <svg viewBox="0 0 220 44" height="36" xmlns="http://www.w3.org/2000/svg" aria-label="Reembolsos">
      <defs>
        <linearGradient id="abagGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#60c8ff" />
          <stop offset="100%" stopColor="#1570b8" />
        </linearGradient>
        <linearGradient id="asGrad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#38bdf8" />
          <stop offset="100%" stopColor="#818cf8" />
        </linearGradient>
      </defs>
      {/* Knot */}
      <ellipse cx="22" cy="12" rx="7" ry="3" fill="#0d5fa8" />
      {/* Neck */}
      <rect x="17" y="12" width="10" height="7" rx="1" fill="url(#abagGrad)" />
      {/* Body */}
      <ellipse cx="22" cy="30" rx="15" ry="13" fill="url(#abagGrad)" />
      {/* Arrow */}
      <path d="M14 33 A9 9 0 0 1 30 33" stroke="white" strokeWidth="2.5" fill="none" strokeLinecap="round" />
      <polygon points="14,28 9,33 14,38" fill="white" />
      {/* Text */}
      <text fontFamily="Arial, sans-serif" fontWeight="bold" fontSize="20" y="34" x="44">
        <tspan fill="white">reembolso</tspan>
        <tspan fill="url(#asGrad)">s</tspan>
      </text>
    </svg>
  );
}

function Layout() {
  const { logout } = useAuth();
  const [pwdOpen, setPwdOpen] = useState(false);

  return (
    <>
      <AppBar position="static">
        <Toolbar>
          <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center' }}>
            <AppLogo />
          </Box>
          <Button color="inherit" component={RouterLink} to="/">Dashboard</Button>
          <Button color="inherit" component={RouterLink} to="/pagos">Pagos</Button>
          <Button color="inherit" component={RouterLink} to="/ajustes">Ajustes</Button>
          <Button color="inherit" onClick={() => setPwdOpen(true)}>Contraseña</Button>
          <Button color="inherit" onClick={logout}>Salir</Button>
        </Toolbar>
      </AppBar>
      <Container maxWidth="lg" sx={{ mt: 3, mb: 3 }}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/pagos" element={<Pagos />} />
          <Route path="/ajustes" element={<Ajustes />} />
        </Routes>
      </Container>
      <CambiarPasswordModal open={pwdOpen} onClose={() => setPwdOpen(false)} />
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
