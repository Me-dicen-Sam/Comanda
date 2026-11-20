# Permite usar MySQL con PyMySQL (instala fácil en Windows, sin compiladores).
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass
