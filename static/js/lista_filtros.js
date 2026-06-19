// ganadoSWG/static/js/lista_filtros.js
// V3: Calendario + recálculo de tarjetas + mejoras visuales
// Recalcula estadísticas automáticamente cuando filtra por mes/año

(function() {
    'use strict';

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initCalendario);
    } else {
        initCalendario();
    }

    function initCalendario() {
        var tablas = document.querySelectorAll('table.table');
        if (tablas.length === 0) return;

        tablas.forEach(function(tabla) {
            var headers = tabla.querySelectorAll('thead th');
            var fechaIndex = -1;
            headers.forEach(function(th, index) {
                var texto = th.textContent.toLowerCase().trim();
                if (texto.includes('fecha') || texto.includes('date') || texto.includes('muestreo')) {
                    fechaIndex = index;
                }
            });

            if (fechaIndex === -1) return;

            var cardBody = tabla.closest('.card-hacienda, .card, .p-3');
            if (!cardBody) return;
            if (cardBody.querySelector('.panel-calendario')) return;

            // === GUARDAR VALORES ORIGINALES DE TARJETAS ===
            var tarjetasInfo = [];
            var tarjetasRow = cardBody.previousElementSibling;
            if (tarjetasRow && tarjetasRow.classList.contains('row')) {
                tarjetasRow.querySelectorAll('.card-hacienda').forEach(function(card) {
                    var h4 = card.querySelector('h4');
                    var small = card.querySelector('small');
                    if (h4 && small) {
                        tarjetasInfo.push({
                            card: card,
                            h4: h4,
                            small: small,
                            originalText: h4.textContent.trim(),
                            label: small.textContent.trim()
                        });
                    }
                });
            }

            // === EXTRAER FECHAS ===
            var fechasMap = [];
            tabla.querySelectorAll('tbody tr').forEach(function(row) {
                var celda = row.cells[fechaIndex];
                if (celda) {
                    var texto = celda.textContent.trim();
                    var fecha = parseFechaRobusto(texto);
                    if (fecha && !isNaN(fecha.getFullYear())) {
                        fechasMap.push({
                            fecha: fecha,
                            row: row,
                            anio: fecha.getFullYear(),
                            mes: fecha.getMonth()
                        });
                    }
                }
            });

            if (fechasMap.length === 0) return;

            // === AGRUPAR ===
            var datos = {};
            fechasMap.forEach(function(item) {
                var a = item.anio, m = item.mes;
                if (!datos[a]) datos[a] = {};
                if (!datos[a][m]) datos[a][m] = { count: 0, rows: [] };
                datos[a][m].count++;
                datos[a][m].rows.push(item.row);
            });

            var mesesNombres = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
                'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];

            // === CREAR PANEL ===
            var panel = document.createElement('div');
            panel.className = 'panel-calendario mb-4';
            panel.style.cssText = 'border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.1);';

            var totalRegistros = fechasMap.length;
            panel.innerHTML =
                '<div style="background: linear-gradient(135deg, #2c5e1a, #1a3d0f); color: white; padding: 14px 18px; font-weight: 700; font-size: 1.05rem; cursor: pointer; display: flex; align-items: center; justify-content: space-between;" data-bs-toggle="collapse" data-bs-target="#calendarioBody">' +
                '   <span><i class="bi bi-calendar3-range me-2"></i>NAVEGAR POR PERÍODO</span>' +
                '   <span style="display: flex; align-items: center; gap: 10px;">' +
                '       <span style="background: rgba(255,255,255,0.25); padding: 4px 12px; border-radius: 20px; font-size: 0.85rem;">' + totalRegistros + ' registros</span>' +
                '       <i class="bi bi-chevron-down" style="transition: transform 0.3s;"></i>' +
                '   </span>' +
                '</div>' +
                '<div class="collapse show" id="calendarioBody">' +
                '   <div style="background: #f5f0e6; padding: 16px;">' +
                '       <div id="calendarioAccordion" style="display: flex; flex-direction: column; gap: 8px;"></div>' +
                '       <div class="mt-3 text-center">' +
                '           <button class="btn limpiar-calendario" type="button" style="background: linear-gradient(135deg, #8B4513, #a0522d); color: white; border: none; border-radius: 8px; padding: 8px 24px; font-weight: 600; box-shadow: 0 4px 10px rgba(139,69,19,0.3);">' +
                '               <i class="bi bi-arrow-counterclockwise me-2"></i>MOSTRAR TODOS' +
                '           </button>' +
                '       </div>' +
                '   </div>' +
                '</div>';

            var accordion = panel.querySelector('#calendarioAccordion');
            var anios = Object.keys(datos).sort(function(a,b){ return b-a; });

            anios.forEach(function(anio) {
                var meses = Object.keys(datos[anio]).sort(function(a,b){ return a-b; });
                var totalAnio = 0;
                meses.forEach(function(m){ totalAnio += datos[anio][m].count; });

                var anioDiv = document.createElement('div');
                anioDiv.style.cssText = 'border: 2px solid #d4c5a9; border-radius: 10px; overflow: hidden; background: white;';

                var anioHeader = document.createElement('div');
                anioHeader.style.cssText = 'background: linear-gradient(135deg, #2c5e1a, #3d7a24); color: white; padding: 10px 16px; font-weight: 700; cursor: pointer; display: flex; align-items: center; justify-content: space-between;';
                anioHeader.innerHTML =
                    '<span style="display: flex; align-items: center; gap: 8px;">' +
                    '   <i class="bi bi-calendar-year" style="font-size: 1.2rem;"></i>' +
                    '   Año ' + anio +
                    '</span>' +
                    '<span style="display: flex; align-items: center; gap: 10px;">' +
                    '   <span style="background: rgba(255,255,255,0.3); padding: 3px 10px; border-radius: 15px; font-size: 0.8rem;">' + totalAnio + ' registros</span>' +
                    '   <i class="bi bi-chevron-down" style="transition: transform 0.3s;"></i>' +
                    '</span>';

                var mesesDiv = document.createElement('div');
                mesesDiv.style.cssText = 'display: none; padding: 12px; background: #faf8f3; border-top: 1px solid #d4c5a9;';

                var grid = document.createElement('div');
                grid.style.cssText = 'display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 8px;';

                meses.forEach(function(mes) {
                    var mesData = datos[anio][mes];
                    var btn = document.createElement('button');
                    btn.setAttribute('data-anio', anio);
                    btn.setAttribute('data-mes', mes);
                    btn.style.cssText = 'border: 2px solid #d4c5a9; border-radius: 8px; padding: 10px 12px; cursor: pointer; background: white; transition: all 0.2s; display: flex; align-items: center; justify-content: space-between; font-size: 0.9rem; font-weight: 600; color: #2c5e1a;';
                    btn.innerHTML =
                        '<span style="display: flex; align-items: center; gap: 6px;">' +
                        '   <i class="bi bi-calendar-month" style="color: #8B4513;"></i>' +
                        '   ' + mesesNombres[mes] +
                        '</span>' +
                        '<span style="background: linear-gradient(135deg, #2c5e1a, #3d7a24); color: white; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 700;">' + mesData.count + '</span>';

                    btn.addEventListener('mouseenter', function(){
                        if (!this.classList.contains('active')) {
                            this.style.background = '#f0ece0';
                            this.style.borderColor = '#2c5e1a';
                        }
                    });
                    btn.addEventListener('mouseleave', function(){
                        if (!this.classList.contains('active')) {
                            this.style.background = 'white';
                            this.style.borderColor = '#d4c5a9';
                        }
                    });

                    btn.addEventListener('click', function() {
                        var anioSel = this.getAttribute('data-anio');
                        var mesSel = this.getAttribute('data-mes');
                        filtrarPorMes(tabla, fechasMap, anioSel, mesSel);

                        // Recalcular tarjetas
                        actualizarTarjetas(tarjetasInfo, tabla, datos, anioSel, mesSel);

                        // Reset estilos
                        grid.querySelectorAll('button').forEach(function(b){
                            b.classList.remove('active');
                            b.style.cssText = 'border: 2px solid #d4c5a9; border-radius: 8px; padding: 10px 12px; cursor: pointer; background: white; transition: all 0.2s; display: flex; align-items: center; justify-content: space-between; font-size: 0.9rem; font-weight: 600; color: #2c5e1a;';
                        });
                        this.classList.add('active');
                        this.style.cssText = 'border: 2px solid #2c5e1a; border-radius: 8px; padding: 10px 12px; cursor: pointer; background: linear-gradient(135deg, #2c5e1a, #3d7a24); transition: all 0.2s; display: flex; align-items: center; justify-content: space-between; font-size: 0.9rem; font-weight: 600; color: white; box-shadow: 0 4px 10px rgba(44,94,26,0.3);';
                    });

                    grid.appendChild(btn);
                });

                mesesDiv.appendChild(grid);
                anioDiv.appendChild(anioHeader);
                anioDiv.appendChild(mesesDiv);
                accordion.appendChild(anioDiv);

                anioHeader.addEventListener('click', function() {
                    var isVisible = mesesDiv.style.display === 'block';
                    mesesDiv.style.display = isVisible ? 'none' : 'block';
                    var chevron = this.querySelector('.bi-chevron-down');
                    chevron.style.transform = isVisible ? 'rotate(0deg)' : 'rotate(180deg)';
                });
            });

            // Insertar
            var tablaParent = tabla.parentNode;
            tablaParent.insertBefore(panel, tabla);

            // Limpiar
            panel.querySelector('.limpiar-calendario').addEventListener('click', function() {
                tabla.querySelectorAll('tbody tr').forEach(function(row) {
                    row.style.display = '';
                });
                grid.querySelectorAll('button').forEach(function(b){
                    b.classList.remove('active');
                    b.style.cssText = 'border: 2px solid #d4c5a9; border-radius: 8px; padding: 10px 12px; cursor: pointer; background: white; transition: all 0.2s; display: flex; align-items: center; justify-content: space-between; font-size: 0.9rem; font-weight: 600; color: #2c5e1a;';
                });
                // Restaurar tarjetas originales
                tarjetasInfo.forEach(function(t) {
                    t.h4.textContent = t.originalText;
                    t.h4.style.color = '';
                    t.small.textContent = t.label;
                });
            });

            // Responsive tabla
            if (!tabla.parentElement.classList.contains('table-responsive')) {
                tabla.parentElement.classList.add('table-responsive');
            }
        });
    }

    // === RECALCULAR TARJETAS SEGÚN FILTRO ===
    function actualizarTarjetas(tarjetasInfo, tabla, datos, anio, mes) {
        if (tarjetasInfo.length === 0) return;

        var anioNum = parseInt(anio);
        var mesNum = parseInt(mes);
        var filasVisibles = [];

        tabla.querySelectorAll('tbody tr').forEach(function(row) {
            if (row.style.display !== 'none') {
                filasVisibles.push(row);
            }
        });

        var total = filasVisibles.length;

        // Buscar el dato de mes correspondiente
        var mesData = null;
        if (datos[anioNum] && datos[anioNum][mesNum]) {
            mesData = datos[anioNum][mesNum];
        }

        tarjetasInfo.forEach(function(t) {
            var label = t.label.toLowerCase();
            var nuevoValor = t.originalText;
            var nuevoLabel = t.label;

            // Si la etiqueta contiene "total" -> mostrar total de filas visibles
            if (label.includes('total') || label.includes('cantidad') || label.includes('registros')) {
                nuevoValor = total;
                nuevoLabel = t.label + ' (filtrado)';
            }
            // Si la etiqueta contiene "litros" y hay suma posible
            else if (label.includes('litros') && label.includes('total')) {
                var suma = 0;
                filasVisibles.forEach(function(row) {
                    var cells = row.querySelectorAll('td');
                    cells.forEach(function(cell) {
                        var num = parseFloat(cell.textContent.replace(/,/g, ''));
                        if (!isNaN(num) && num > 0) {
                            suma += num;
                        }
                    });
                });
                if (suma > 0) nuevoValor = suma.toFixed(2);
                nuevoLabel = t.label + ' (filtrado)';
            }

            // Si no hay datos (total = 0), mostrar en gris
            if (total === 0) {
                t.h4.textContent = '-';
                t.h4.style.color = '#999';
                t.small.textContent = 'Sin registros en este período';
            } else {
                t.h4.textContent = nuevoValor;
                t.h4.style.color = 'var(--color-primario)';
                t.small.textContent = nuevoLabel;
            }
        });
    }

    // === FILTRAR ===
    function filtrarPorMes(tabla, fechasMap, anio, mes) {
        var anioNum = parseInt(anio);
        var mesNum = parseInt(mes);
        fechasMap.forEach(function(item) {
            if (item.anio === anioNum && item.mes === mesNum) {
                item.row.style.display = '';
            } else {
                item.row.style.display = 'none';
            }
        });
    }

    // === PARSEO ROBUSTO ===
    function parseFechaRobusto(texto) {
        if (!texto) return null;
        texto = texto.trim();
        var iso = texto.match(/^(\d{4})-(\d{2})-(\d{2})/);
        if (iso) {
            var d = new Date(parseInt(iso[1]), parseInt(iso[2])-1, parseInt(iso[3]));
            if (!isNaN(d.getTime())) return d;
        }
        var dmy = texto.match(/^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})/);
        if (dmy) {
            var d = new Date(parseInt(dmy[3]), parseInt(dmy[2])-1, parseInt(dmy[1]));
            if (!isNaN(d.getTime())) return d;
        }
        var d = new Date(texto);
        if (!isNaN(d.getTime())) return d;
        return null;
    }
})();
