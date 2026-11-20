// Solo hace falta si quieres CAMBIAR estilos: el CSS ya viene compilado en static/css/tailwind.css
module.exports = {
  content: [
    './templates/**/*.html',
    './accounts/**/*.py', './catalogo/**/*.py', './paneles/**/*.py', './pedidos/**/*.py', './simulacion/**/*.py',
  ],
  theme: { extend: {} },
};
