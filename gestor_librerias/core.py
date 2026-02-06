import subprocess
import sys
import json
import urllib.request
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Tuple, List
import importlib.metadata

# =========================
# Enums y Dataclasses
# =========================

class ModoOperacion(Enum):
    """Define los modos de operación disponibles."""
    SOLO_VER = "solo_ver"
    INSTALAR = "instalar"
    INSTALAR_Y_ACTUALIZAR = "instalar_y_actualizar"

class EstadoLibreria(Enum):
    """Estados posibles de una librería."""
    NO_INSTALADA = "no_instalada"
    INSTALADA = "instalada"
    ACTUALIZADA = "actualizada"
    ERROR = "error"

@dataclass(frozen=True)
class ConfigModo:
    """Configuración para cada modo de operación."""
    solo_verificar: bool
    actualizar: bool
    descripcion: str

@dataclass
class InfoLibreria:
    """Información detallada de una librería."""
    libreria: str
    estado: EstadoLibreria
    version_instalada: Optional[str] = None
    ultima_version: Optional[str] = None
    mensaje: Optional[str] = None
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            object.__setattr__(self, 'timestamp', datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        """Convierte la info a diccionario para JSON."""
        resultado = {
            'libreria': self.libreria,
            'estado': self.estado.value,
            'timestamp': self.timestamp
        }
        if self.version_instalada:
            resultado['version_instalada'] = self.version_instalada
        if self.ultima_version:
            resultado['ultima_version'] = self.ultima_version
        if self.mensaje:
            resultado['mensaje'] = self.mensaje
        return resultado

# =========================
# Configuración de Modos
# =========================

CONFIG_MODOS: Dict[ModoOperacion, ConfigModo] = {
    ModoOperacion.SOLO_VER: ConfigModo(
        solo_verificar=True,
        actualizar=False,
        descripcion="Solo verifica si la librería está instalada y guarda info en JSON."
    ),
    ModoOperacion.INSTALAR: ConfigModo(
        solo_verificar=False,
        actualizar=False,
        descripcion="Instala la librería si no está instalada, no actualiza."
    ),
    ModoOperacion.INSTALAR_Y_ACTUALIZAR: ConfigModo(
        solo_verificar=False,
        actualizar=True,
        descripcion="Instala la librería si no está, y actualiza si ya existe."
    ),
}

# =========================
# Clases de Servicio
# =========================

class ConsultorVersiones:
    """Maneja consultas de versiones de librerías."""

    @staticmethod
    def obtener_version_instalada(nombre_libreria: str) -> str:
        """Devuelve la versión instalada de la librería."""
        try:
            resultado = subprocess.check_output(
                [sys.executable, "-m", "pip", "show", nombre_libreria],
                text=True,
                stderr=subprocess.DEVNULL
            )
            for linea in resultado.splitlines():
                if linea.startswith("Version:"):
                    return linea.split(":", 1)[1].strip()
        except subprocess.CalledProcessError:
            pass
        return "desconocida"

    @staticmethod
    def obtener_ultima_version(nombre_libreria: str) -> str:
        """Devuelve la última versión disponible en PyPI."""
        try:
            url = f"https://pypi.org/pypi/{nombre_libreria}/json"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.load(response)
                return data["info"]["version"]
        except Exception:
            return "desconocida"

class GestorJSON:
    """Maneja la persistencia de datos en archivos JSON."""

    def __init__(self, archivo: str = "librerias_verificadas.json"):
        self.ruta = Path(archivo)

    def leer(self) -> Dict:
        """Lee el contenido del archivo JSON."""
        if self.ruta.exists():
            try:
                return json.loads(self.ruta.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {}
        return {}

    def guardar(self, contenido: Dict) -> None:
        """Guarda el contenido en el archivo JSON."""
        self.ruta.write_text(
            json.dumps(contenido, indent=4, ensure_ascii=False),
            encoding="utf-8"
        )

    def actualizar_libreria(self, info: InfoLibreria) -> None:
        """Actualiza la información de una librería en el JSON."""
        contenido = self.leer()
        contenido[info.libreria] = info.to_dict()
        self.guardar(contenido)

class InstaladorPip:
    """Maneja instalación y verificación de paquetes con pip de forma robusta."""

    @staticmethod
    def esta_instalada(nombre_libreria: str) -> bool:
        """
        Verifica si una librería está instalada consultando los metadatos del sistema.
        Es compatible con nombres como 'yt-dlp', 'scikit-learn', etc.
        """
        try:
            # metadata.version busca el nombre tal cual aparece en pip list/show
            importlib.metadata.version(nombre_libreria)
            return True
        except importlib.metadata.PackageNotFoundError:
            # Si no la encuentra, probamos normalizando guiones por si acaso
            try:
                importlib.metadata.version(nombre_libreria.replace("-", "_"))
                return True
            except importlib.metadata.PackageNotFoundError:
                return False

    @staticmethod
    def instalar(nombre_libreria: str) -> None:
        """Instala una librería usando pip."""
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", nombre_libreria],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )

    @staticmethod
    def actualizar(nombre_libreria: str) -> None:
        """Actualiza una librería usando pip."""
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--upgrade", nombre_libreria],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )

class FormateadorSalida:
    """Formatea y muestra mensajes en consola."""

    ICONOS = {
        'exito': '✔',
        'error': '❌',
        'instalando': '⬇',
        'actualizando': '🔄',
        'paquete': '📦',
        'web': '🌐',
        'guardado': '💾',
        'completado': '✅'
    }

    @classmethod
    def mostrar_no_instalada(cls, nombre: str, guardar_json: bool, archivo: str):
        """Muestra mensaje cuando la librería no está instalada."""
        print(f"{cls.ICONOS['error']} La librería '{nombre}' no está instalada.")
        if guardar_json:
            print(f"{cls.ICONOS['guardado']} Información guardada en '{archivo}'\n")

    @classmethod
    def mostrar_instalada(cls, nombre: str, version_instalada: str, 
                          ultima_version: str, guardar_json: bool, archivo: str):
        """Muestra información de librería instalada."""
        print(f"{cls.ICONOS['exito']} '{nombre}' instalada")
        print(f"{cls.ICONOS['paquete']} Versión instalada: {version_instalada}")
        print(f"{cls.ICONOS['web']} Última versión: {ultima_version}")
        if guardar_json:
            print(f"{cls.ICONOS['guardado']} Información guardada en '{archivo}'\n")

    @classmethod
    def mostrar_instalando(cls, nombre: str):
        """Muestra mensaje de instalación."""
        print(f"{cls.ICONOS['instalando']} '{nombre}' no está instalada. Instalando...")

    @classmethod
    def mostrar_actualizando(cls, nombre: str):
        """Muestra mensaje de actualización."""
        print(f"{cls.ICONOS['actualizando']} Actualizando '{nombre}'...")

    @classmethod
    def mostrar_completado(cls, nombre: str, guardar_json: bool, archivo: str):
        """Muestra mensaje de proceso completado."""
        print(f"{cls.ICONOS['completado']} Proceso completado para '{nombre}'.")
        if guardar_json:
            print(f"{cls.ICONOS['guardado']} Información guardada en '{archivo}'\n")

    @classmethod
    def mostrar_error(cls, nombre: str, error: str, guardar_json: bool, archivo: str):
        """Muestra mensaje de error."""
        print(f"{cls.ICONOS['error']} Error con '{nombre}': {error}")
        if guardar_json:
            print(f"{cls.ICONOS['guardado']} Error guardado en '{archivo}'\n")

# =========================
# Clase Principal
# =========================

class VerificadorLibrerias:
    """
    Gestiona la verificación, instalación y actualización de librerías Python.
    """

    def __init__(self, archivo_json: str = "librerias_verificadas.json"):
        self.gestor_json = GestorJSON(archivo_json)
        self.instalador = InstaladorPip()
        self.consultor = ConsultorVersiones()
        self.formateador = FormateadorSalida()
        self.archivo_json = archivo_json

    def verificar(
        self,
        nombre_libreria: str,
        modo: ConfigModo,
        guardar_json: bool = True
    ) -> Tuple[bool, InfoLibreria]:
        """
        Verifica, instala o actualiza una librería según el modo.

        Args:
            nombre_libreria: Nombre del paquete
            modo: Configuración del modo de operación
            guardar_json: Si se debe guardar la información en JSON

        Returns:
            Tuple[bool, InfoLibreria]: (éxito, información de la librería)
        """
        try:
            instalada = self.instalador.esta_instalada(nombre_libreria)

            if modo.solo_verificar:
                return self._verificar_solo(nombre_libreria, instalada, guardar_json)
            else:
                return self._verificar_e_instalar(
                    nombre_libreria, instalada, modo.actualizar, guardar_json
                )

        except Exception as e:
            return self._manejar_error(nombre_libreria, e, guardar_json)

    def _verificar_solo(
        self, 
        nombre: str, 
        instalada: bool, 
        guardar_json: bool
    ) -> Tuple[bool, InfoLibreria]:
        """Verifica el estado de la librería sin modificarla."""
        
        if not instalada:
            info = InfoLibreria(
                libreria=nombre,
                estado=EstadoLibreria.NO_INSTALADA,
                mensaje=f"La librería '{nombre}' no está instalada."
            )
            if guardar_json:
                self.gestor_json.actualizar_libreria(info)

            self.formateador.mostrar_no_instalada(nombre, guardar_json, self.archivo_json)
            return True, info

        version_instalada = self.consultor.obtener_version_instalada(nombre)
        ultima_version = self.consultor.obtener_ultima_version(nombre)

        info = InfoLibreria(
            libreria=nombre,
            estado=EstadoLibreria.INSTALADA,
            version_instalada=version_instalada,
            ultima_version=ultima_version
        )

        if guardar_json:
            self.gestor_json.actualizar_libreria(info)

        self.formateador.mostrar_instalada(
            nombre, version_instalada, ultima_version, guardar_json, self.archivo_json
        )
        return True, info

    def _verificar_e_instalar(
        self,
        nombre: str,
        instalada: bool,
        actualizar: bool,
        guardar_json: bool
    ) -> Tuple[bool, InfoLibreria]:
        """Instala o actualiza la librería según sea necesario."""
        estado_final = EstadoLibreria.INSTALADA

        if instalada:
            print(f"{self.formateador.ICONOS['exito']} '{nombre}' ya está instalada.")
            if actualizar:
                self.formateador.mostrar_actualizando(nombre)
                self.instalador.actualizar(nombre)
                estado_final = EstadoLibreria.ACTUALIZADA
        else:
            self.formateador.mostrar_instalando(nombre)
            self.instalador.instalar(nombre)

        version_instalada = self.consultor.obtener_version_instalada(nombre)
        ultima_version = self.consultor.obtener_ultima_version(nombre)

        info = InfoLibreria(
            libreria=nombre,
            estado=estado_final,
            version_instalada=version_instalada,
            ultima_version=ultima_version
        )

        if guardar_json:
            self.gestor_json.actualizar_libreria(info)

        self.formateador.mostrar_completado(nombre, guardar_json, self.archivo_json)
        return True, info

    def _manejar_error(
        self,
        nombre: str,
        error: Exception,
        guardar_json: bool
    ) -> Tuple[bool, InfoLibreria]:
        """Maneja errores durante la operación."""
        info = InfoLibreria(
            libreria=nombre,
            estado=EstadoLibreria.ERROR,
            mensaje=str(error)
        )

        if guardar_json:
            self.gestor_json.actualizar_libreria(info)

        self.formateador.mostrar_error(nombre, str(error), guardar_json, self.archivo_json)
        return False, info

# =========================
# Validadores y Utilidades
# =========================

class Validador:
    """Valida entradas del usuario."""

    @staticmethod
    def validar_nombre_libreria(nombre: str) -> str:
        """Valida el nombre de la librería."""
        if not isinstance(nombre, str) or not nombre.strip():
            raise ValueError("Se debe proporcionar un nombre de librería válido.")
        return nombre.strip()

    @staticmethod
    def parsear_bool(valor: str) -> bool:
        """Convierte string a booleano."""
        if isinstance(valor, bool):
            return valor

        if not isinstance(valor, str):
            raise ValueError("guardar_json debe ser exactamente 'si' o 'no'.")

        valor_normalizado = valor.strip().lower()

        if valor_normalizado not in ("si", "no"):
            raise ValueError(
                f"Valor inválido: '{valor}'. Debe ser exactamente 'si' o 'no'."
            )

        return valor_normalizado == "si"

    @staticmethod
    def obtener_modo(opcion: str) -> ConfigModo:
        """Obtiene la configuración del modo de operación."""
        try:
            modo_enum = ModoOperacion(opcion)
            return CONFIG_MODOS[modo_enum]
        except ValueError:
            opciones_validas = [m.value for m in ModoOperacion]
            raise ValueError(
                f"Opción inválida: '{opcion}'. Debe ser una de: {opciones_validas}"
            )
    
# =========================
# Función Principal
# =========================

def main(
    libreria_a_verificar: str,
    opcion: str = ModoOperacion.SOLO_VER.value,
    guardar_json: str = "si",
    archivo_json: str = "librerias_verificadas.json"
):
    """
    Punto de entrada principal con reporte extendido de resultados.
    """
    try:
        # 1. Validación de entradas
        nombre_libreria = Validador.validar_nombre_libreria(libreria_a_verificar)
        guardar_json_bool = Validador.parsear_bool(guardar_json)
        modo = Validador.obtener_modo(opcion)

        # 2. Ejecución de la lógica central
        verificador = VerificadorLibrerias(archivo_json)
        exito, info = verificador.verificar(nombre_libreria, modo, guardar_json_bool)

        if not exito:
            raise RuntimeError(
                f"No se pudo completar la operación sobre '{nombre_libreria}'. "
                f"Detalle: {info.mensaje}"
            )
        
        print(f"✔ El proceso para '{nombre_libreria}' ha finalizado.\n")
        
    except Exception as e:
        # Reporte de error crítico
        print(f"\n❌ ERROR CRÍTICO: {e}")
        raise RuntimeError(f"Fallo en la ejecución: {e}") from e
        
class ListarLibrerias:
    """
    Clase encargada de listar y filtrar las librerías instaladas en el entorno actual.
    """

    @staticmethod
    def obtener_todas() -> List[Dict[str, str]]:
        """
        Retorna una lista de diccionarios con el nombre y la versión de 
        todas las librerías instaladas.
        """
        librerias = []
        # Iteramos sobre todas las distribuciones instaladas en el path actual
        for dist in sorted(importlib.metadata.distributions(), key=lambda x: x.metadata['Name'].lower()):
            librerias.append({
                "nombre": dist.metadata['Name'],
                "version": dist.version
            })
        return librerias

    @classmethod
    def buscar_por_nombre(cls, patron: str) -> List[Dict[str, str]]:
        """
        Busca librerías cuyo nombre contenga el patrón indicado (case-insensitive).
        """
        todas = cls.obtener_todas()
        patron = patron.lower()
        return [lib for lib in todas if patron in lib['nombre'].lower()]

    @classmethod
    def mostrar_resumen(
        cls, 
        guardar_json: bool = False, 
        gestor_json: Optional['GestorJSON'] = GestorJSON(), 
        nombre_archivo: str = "inventario_entorno.json"
    ):
        """
        Imprime en consola una tabla con las librerías y, opcionalmente, exporta a JSON.
        
        Args:
            guardar_json: Si es True, invoca exportar_a_json.
            gestor_json: Instancia de GestorJSON necesaria si guardar_json es True.
            nombre_archivo: Nombre del archivo de destino.
        """
        librerias = cls.obtener_todas()
        
        # Formateo de tabla en consola
        print(f"\n{'LIBRERÍA':<35} | {'VERSIÓN':<15}")
        print("-" * 55)
        for lib in librerias:
            print(f"{lib['nombre']:<35} | {lib['version']:<15}")
        print("-" * 55)
        print(f"Total de librerías detectadas: {len(librerias)}\n")

        # Lógica de exportación integrada
        if guardar_json:
            if gestor_json is None:
                print("❌ Error: Se requiere una instancia de 'GestorJSON' para exportar.")
            else:
                cls.exportar_a_json(gestor_json, nombre_archivo)

    @classmethod
    def exportar_a_json(cls, gestor_json: 'GestorJSON', nombre_archivo: str = "inventario_entorno.json"):
        """
        Exporta el listado actual a un archivo JSON utilizando el GestorJSON existente.
        """
        datos = {
            "fecha_escaneo": datetime.utcnow().isoformat(),
            "total_librerias": 0,
            "librerias": cls.obtener_todas()
        }
        datos["total_librerias"] = len(datos["librerias"])
        
        # Configuración dinámica del gestor
        gestor_json.ruta = Path(nombre_archivo)
        gestor_json.guardar(datos)
        print(f"💾 Inventario exportado correctamente a: {nombre_archivo}")

# =========================
# Ejecución
# =========================

if __name__ == "__main__":

    main("wheel", opcion="solo_ver", guardar_json="si")

#ListarLibrerias.mostrar_resumen()