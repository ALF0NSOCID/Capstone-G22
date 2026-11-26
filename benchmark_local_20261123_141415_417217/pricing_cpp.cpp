#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <cmath>
#include <functional>
#include <limits>
#include <queue>
#include <stdexcept>
#include <string>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>

namespace py = pybind11;

namespace {

constexpr double EPSILON_RELAJACION = 1e-15;

struct Arista {
    int destino;
    int id;
};

struct Producto {
    int id;
    int origen;
    int destino;
};

struct GrupoOrigen {
    int origen;
    std::vector<std::size_t> indices_productos;
};

using ResultadoCamino = std::tuple<int, double, std::vector<int>>;

class MotorCaminos {
public:
    MotorCaminos(
        int numero_nodos,
        const std::vector<int>& origen_arcos,
        const std::vector<int>& destino_arcos,
        const std::vector<int>& ids_productos,
        const std::vector<int>& origen_productos,
        const std::vector<int>& destino_productos
    ) : numero_nodos_(numero_nodos), numero_arcos_(origen_arcos.size()) {
        if (numero_nodos_ < 1) {
            throw std::invalid_argument("El numero de nodos debe ser positivo.");
        }
        if (origen_arcos.size() != destino_arcos.size()) {
            throw std::invalid_argument(
                "Los vectores de origen y destino de arcos tienen distinto tamano."
            );
        }
        if (
            ids_productos.size() != origen_productos.size()
            || ids_productos.size() != destino_productos.size()
        ) {
            throw std::invalid_argument(
                "Los vectores de productos tienen distinto tamano."
            );
        }

        adyacencia_.resize(static_cast<std::size_t>(numero_nodos_) + 1);
        for (std::size_t arco = 0; arco < numero_arcos_; ++arco) {
            const int origen = origen_arcos[arco];
            const int destino = destino_arcos[arco];
            validar_nodo(origen, "origen de arco");
            validar_nodo(destino, "destino de arco");
            adyacencia_[origen].push_back(
                Arista{destino, static_cast<int>(arco)}
            );
        }

        productos_.reserve(ids_productos.size());
        std::unordered_map<int, std::size_t> indice_grupo;

        for (std::size_t i = 0; i < ids_productos.size(); ++i) {
            const int origen = origen_productos[i];
            const int destino = destino_productos[i];
            validar_nodo(origen, "origen de producto");
            validar_nodo(destino, "destino de producto");

            productos_.push_back(Producto{ids_productos[i], origen, destino});

            auto encontrado = indice_grupo.find(origen);
            if (encontrado == indice_grupo.end()) {
                const std::size_t nuevo_indice = grupos_.size();
                indice_grupo.emplace(origen, nuevo_indice);
                grupos_.push_back(GrupoOrigen{origen, {i}});
            } else {
                grupos_[encontrado->second].indices_productos.push_back(i);
            }
        }

        distancia_.resize(static_cast<std::size_t>(numero_nodos_) + 1);
        predecesor_nodo_.resize(static_cast<std::size_t>(numero_nodos_) + 1);
        predecesor_arco_.resize(static_cast<std::size_t>(numero_nodos_) + 1);
    }

    std::vector<ResultadoCamino> caminos_minimos(
        const std::vector<double>& pesos
    ) {
        validar_pesos(pesos);
        std::vector<ResultadoCamino> resultados;
        resultados.reserve(productos_.size());

        for (const auto& grupo : grupos_) {
            ejecutar_dijkstra(grupo.origen, pesos);

            for (const std::size_t indice : grupo.indices_productos) {
                const Producto& producto = productos_[indice];
                resultados.emplace_back(
                    producto.id,
                    distancia_producto(producto),
                    reconstruir_camino(producto)
                );
            }
        }

        return resultados;
    }

    std::tuple<double, std::vector<ResultadoCamino>> pricing(
        const std::vector<double>& pesos,
        const std::vector<double>& duales_productos,
        double tolerancia
    ) {
        validar_pesos(pesos);
        if (duales_productos.size() != productos_.size()) {
            throw std::invalid_argument(
                "La cantidad de duales no coincide con la cantidad de productos."
            );
        }
        if (tolerancia < 0.0 || !std::isfinite(tolerancia)) {
            throw std::invalid_argument("La tolerancia debe ser finita y no negativa.");
        }

        double menor_costo_reducido = 0.0;
        std::vector<ResultadoCamino> candidatas;

        for (const auto& grupo : grupos_) {
            ejecutar_dijkstra(grupo.origen, pesos);

            for (const std::size_t indice : grupo.indices_productos) {
                const Producto& producto = productos_[indice];
                const double precio_ruta = distancia_producto(producto);
                const double costo_reducido = precio_ruta - duales_productos[indice];
                menor_costo_reducido = std::min(
                    menor_costo_reducido,
                    costo_reducido
                );

                // El camino solo se reconstruye cuando realmente puede entrar
                // al maestro restringido.
                if (costo_reducido < -tolerancia) {
                    candidatas.emplace_back(
                        producto.id,
                        precio_ruta,
                        reconstruir_camino(producto)
                    );
                }
            }
        }

        return {menor_costo_reducido, std::move(candidatas)};
    }

    std::vector<ResultadoCamino> caminos_iniciales_congestion(
        const std::vector<double>& pesos_base,
        const std::vector<double>& capacidades,
        const std::vector<double>& demandas,
        double eta
    ) {
        validar_pesos(pesos_base);
        if (capacidades.size() != numero_arcos_) {
            throw std::invalid_argument(
                "La cantidad de capacidades no coincide con la cantidad de arcos."
            );
        }
        if (demandas.size() != productos_.size()) {
            throw std::invalid_argument(
                "La cantidad de demandas no coincide con la cantidad de productos."
            );
        }
        if (eta < 0.0 || !std::isfinite(eta)) {
            throw std::invalid_argument("Eta debe ser finito y no negativo.");
        }
        for (const double capacidad : capacidades) {
            if (!(capacidad > 0.0) || !std::isfinite(capacidad)) {
                throw std::invalid_argument(
                    "Todas las capacidades deben ser finitas y positivas."
                );
            }
        }

        std::vector<double> carga(numero_arcos_, 0.0);
        std::vector<double> pesos_actuales = pesos_base;
        std::vector<ResultadoCamino> resultados;
        resultados.reserve(productos_.size());

        std::vector<std::size_t> orden_grupos(grupos_.size());
        for (std::size_t i = 0; i < orden_grupos.size(); ++i) {
            orden_grupos[i] = i;
        }
        std::sort(
            orden_grupos.begin(),
            orden_grupos.end(),
            [this](std::size_t a, std::size_t b) {
                return grupos_[a].origen < grupos_[b].origen;
            }
        );

        for (const std::size_t indice_grupo : orden_grupos) {
            const GrupoOrigen& grupo = grupos_[indice_grupo];
            ejecutar_dijkstra(grupo.origen, pesos_actuales);

            std::vector<std::size_t> indices = grupo.indices_productos;
            std::sort(
                indices.begin(),
                indices.end(),
                [this](std::size_t a, std::size_t b) {
                    return productos_[a].id < productos_[b].id;
                }
            );

            for (const std::size_t indice : indices) {
                const Producto& producto = productos_[indice];
                std::vector<int> camino = reconstruir_camino(producto);
                const double demanda = demandas[indice];
                if (!(demanda >= 0.0) || !std::isfinite(demanda)) {
                    throw std::invalid_argument(
                        "Todas las demandas deben ser finitas y no negativas."
                    );
                }

                for (const int arco : camino) {
                    carga[static_cast<std::size_t>(arco)] += demanda;
                }
                resultados.emplace_back(
                    producto.id,
                    distancia_producto(producto),
                    std::move(camino)
                );
            }

            for (std::size_t arco = 0; arco < numero_arcos_; ++arco) {
                const double utilizacion = carga[arco] / capacidades[arco];
                pesos_actuales[arco] = pesos_base[arco]
                    * (1.0 + eta * utilizacion);
            }
        }

        return resultados;
    }

private:
    int numero_nodos_;
    std::size_t numero_arcos_;
    std::vector<std::vector<Arista>> adyacencia_;
    std::vector<Producto> productos_;
    std::vector<GrupoOrigen> grupos_;

    // Se reutilizan en cada ejecucion para evitar reservar memoria por origen.
    std::vector<double> distancia_;
    std::vector<int> predecesor_nodo_;
    std::vector<int> predecesor_arco_;

    void validar_nodo(int nodo, const std::string& descripcion) const {
        if (nodo < 1 || nodo > numero_nodos_) {
            throw std::invalid_argument(
                descripcion + " fuera de rango: " + std::to_string(nodo)
            );
        }
    }

    void validar_pesos(const std::vector<double>& pesos) const {
        if (pesos.size() != numero_arcos_) {
            throw std::invalid_argument(
                "La cantidad de pesos no coincide con la cantidad de arcos."
            );
        }
        for (const double peso : pesos) {
            if (peso < 0.0 || !std::isfinite(peso)) {
                throw std::invalid_argument(
                    "Dijkstra requiere pesos finitos y no negativos."
                );
            }
        }
    }

    void ejecutar_dijkstra(
        int origen,
        const std::vector<double>& pesos
    ) {
        const double infinito = std::numeric_limits<double>::infinity();
        std::fill(distancia_.begin(), distancia_.end(), infinito);
        std::fill(predecesor_nodo_.begin(), predecesor_nodo_.end(), -1);
        std::fill(predecesor_arco_.begin(), predecesor_arco_.end(), -1);

        using ElementoCola = std::pair<double, int>;
        std::priority_queue<
            ElementoCola,
            std::vector<ElementoCola>,
            std::greater<ElementoCola>
        > cola;

        distancia_[origen] = 0.0;
        cola.emplace(0.0, origen);

        while (!cola.empty()) {
            const auto [distancia_actual, nodo] = cola.top();
            cola.pop();

            if (distancia_actual > distancia_[nodo]) {
                continue;
            }

            for (const Arista& arista : adyacencia_[nodo]) {
                const double nueva_distancia = distancia_actual
                    + pesos[static_cast<std::size_t>(arista.id)];

                if (
                    nueva_distancia
                    < distancia_[arista.destino] - EPSILON_RELAJACION
                ) {
                    distancia_[arista.destino] = nueva_distancia;
                    predecesor_nodo_[arista.destino] = nodo;
                    predecesor_arco_[arista.destino] = arista.id;
                    cola.emplace(nueva_distancia, arista.destino);
                }
            }
        }
    }

    double distancia_producto(const Producto& producto) const {
        const double distancia = distancia_[producto.destino];
        if (!std::isfinite(distancia)) {
            throw std::runtime_error(
                "No existe camino para el producto "
                + std::to_string(producto.id) + ": "
                + std::to_string(producto.origen) + " -> "
                + std::to_string(producto.destino)
            );
        }
        return distancia;
    }

    std::vector<int> reconstruir_camino(const Producto& producto) const {
        std::vector<int> camino;
        int nodo = producto.destino;

        while (nodo != producto.origen) {
            const int arco = predecesor_arco_[nodo];
            const int anterior = predecesor_nodo_[nodo];
            if (arco < 0 || anterior < 0) {
                throw std::runtime_error(
                    "No se pudo reconstruir el camino del producto "
                    + std::to_string(producto.id)
                );
            }
            camino.push_back(arco);
            nodo = anterior;
        }

        std::reverse(camino.begin(), camino.end());
        return camino;
    }
};

}  // namespace

PYBIND11_MODULE(pricing_cpp, modulo) {
    modulo.doc() = "Motor C++ de caminos minimos para generacion de columnas";

    py::class_<MotorCaminos>(modulo, "MotorCaminos")
        .def(
            py::init<
                int,
                const std::vector<int>&,
                const std::vector<int>&,
                const std::vector<int>&,
                const std::vector<int>&,
                const std::vector<int>&
            >(),
            py::arg("numero_nodos"),
            py::arg("origen_arcos"),
            py::arg("destino_arcos"),
            py::arg("ids_productos"),
            py::arg("origen_productos"),
            py::arg("destino_productos")
        )
        .def(
            "caminos_minimos",
            &MotorCaminos::caminos_minimos,
            py::arg("pesos")
        )
        .def(
            "pricing",
            &MotorCaminos::pricing,
            py::arg("pesos"),
            py::arg("duales_productos"),
            py::arg("tolerancia")
        )
        .def(
            "caminos_iniciales_congestion",
            &MotorCaminos::caminos_iniciales_congestion,
            py::arg("pesos_base"),
            py::arg("capacidades"),
            py::arg("demandas"),
            py::arg("eta")
        );
}
