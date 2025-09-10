// Modifica la función para cargar datos desde un archivo CSV
$.get('C:\Users\hugo.ibarra\AreaPruebas\static\jsdatos.csv', function(data) {
    // Parsea los datos CSV
    var rows = data.split('\n');
    var tipsData = [];
    for (var i = 0; i < rows.length; i++) {
        var row = rows[i].split(',');
        tipsData.push(row);
    }
    
    // Establece los datos en la propiedad pivotUtilities.tipsData
    $.pivotUtilities.tipsData = tipsData;
    
    // Ahora puedes utilizar los datos cargados desde el archivo CSV
});

