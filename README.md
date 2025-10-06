## Dashboard for nysgjerrigperer og masterstudenter med konkurranseinstinkt og/eller motivasjonsvansker

![Skjermbilde](skjermbilde.png)

Bruker Python, Flask, med en SQL database.

Kjør fila app.py

Gå til typ http://localhost:5000/ 

app.py starter en meny i terminalen, der du enten kan ha vanlig modus der den lytterr etter RFID-scan (alternativt bare skriv inn din ID + ENTER), eller legge til en ny bruker

Nettsida oppdateres med et par sekunders intervall.


attendance.db er databasen for alle scanna oppmøter og registrerte brukere

users.csv er en tabell der man kan legge til bruker, de blir så lagt til i selve databasen når app.py startes. strengt tatt ikke nødvendig, men blir litt idiotsikring mens man kødder rundt med databasen da


#### Hvordan kjøre programmet så det er tilgjengelig eksternt på det lokale nettverket

0. Finn ut IP-adressen til denne enheten, Raspberry Pi 5 i dette tilfellet:
```hostname -I``` gir ```10.53.50.34 2001:700:300:17b6:8d3b:8ada:1ec7:425```, der ```10.53.50.34``` er IP-adressen. 

1. Kjør python-programmet. Inneholder linjen ```app.run(host='0.0.0.0', port=5000)```. 0.0.0.0 gjør appen tilgjengelig på det lokale nettverket. port kan være hva du vil, 5000 er default.

2. På en annen enhet tilkoblet det samme nettverket, naviger til http://IPadresse:port. Eksempel: ```http://10.53.50.34:5000```

3. Suksess