import { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Pagos from './pages/Pagos';
import Ajustes from './pages/Ajustes';
import {
  AppBar, Toolbar, Typography, Button, Box, Container,
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

function Layout() {
  const { logout } = useAuth();
  const [pwdOpen, setPwdOpen] = useState(false);

  return (
    <>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            Control de Reembolsos
          </Typography>
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
