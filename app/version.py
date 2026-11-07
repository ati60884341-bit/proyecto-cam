"""Version de ESTE codigo, para que app/services/actualizador.py sepa si lo
que hay publicado en GitHub Releases es mas nuevo. Hay que subirla a mano
en cada release (junto con installer.iss, que tiene su propio
MyAppVersion - los dos deben decir lo mismo) y crear el tag/release en
GitHub con ese mismo numero, ej.:

    git tag v1.1.0 && git push origin v1.1.0
    gh release create v1.1.0 installer_output/ProyectoCAM_Setup.exe --notes "..."
"""

VERSION = "1.1.0"
