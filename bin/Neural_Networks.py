import pandas as pd
import numpy as np
from CSV_Converter import createCSVDataset
from sklearn.model_selection import train_test_split
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, Dense
from tensorflow.keras.optimizers import Adam

autoencoder = None
rating_matrix = None
restaurants_df = None

def train_autoencoder(restaurant_file='dataset/restaurantList.csv',
                      ratings_file='dataset/userRatings.csv',
                      epochs=50, batch_size=32):
    """Allena un autoencoder per il sistema di raccomandazione."""
    global autoencoder, rating_matrix, restaurants_df

    try:
        restaurants_df = pd.read_csv(restaurant_file)
        ratings = pd.read_csv(ratings_file)
    except FileNotFoundError:
        print(f"\n[❌] Errore: Uno o entrambi i file non trovati: {restaurant_file}, {ratings_file}")
        print(f"Tentativo di conversione di file JSON in CSV in corso...")
        createCSVDataset("dataset/restaurantList.json")
        createCSVDataset("dataset/userRatings.json")
        return

    # Trasformazioni di dati per uso dell'encoder
    ratings['restaurant_id'] = ratings['restaurant_id'].astype(int)
    user_ids = ratings['user_id'].astype('category').cat.codes
    restaurant_ids = ratings['restaurant_id'].astype('category').cat.codes

    # Aggiunta di colonne coi dati trasformati
    ratings['user_id_mapped'] = user_ids
    ratings['restaurant_id_mapped'] = restaurant_ids

    # Calcolo del numero di utenti e ristoranti univoci
    num_users = user_ids.nunique()
    num_restaurants = restaurant_ids.nunique()

    # Creo una matrice di dimensioni pari ai valori appena calcolati e la popolo
    rating_matrix = np.zeros((num_users, num_restaurants))
    for row in ratings.itertuples():
        rating_matrix[row.user_id_mapped, row.restaurant_id_mapped] = row.rating

    # Divido in porzione per allenamento e test, 
    # il seed è impostato a un valore fisso per il testing, ma può essere cambiato
    train_data, test_data = train_test_split(rating_matrix, test_size=0.2, random_state=42)
    
    # Vettore per memorizzare le preferenze dell'utente
    input_layer = Input(shape=(num_restaurants,))

    # L'autoencoder viene creato a due stati (per en/decoder) con 64 e 32 neuroni e codifica i dati ricevuti in input.
    # Dopo ciò, imposto l'autoencoder per tipo di ottimizzatore, tipo di perdita e rateo di apprendimento
    encoded = Dense(64, activation='relu')(input_layer)
    encoded = Dense(32, activation='relu')(encoded)
    decoded = Dense(64, activation='relu')(encoded)
    decoded = Dense(num_restaurants, activation='linear')(decoded)
    autoencoder = Model(input_layer, decoded)
    autoencoder.compile(optimizer=Adam(learning_rate=0.001), loss='mean_squared_error')

    # Normalizzo i dati contenuti nei set per scalare i valori tra 0 e 1
    max_rating = np.max(train_data)
    train_data_norm = train_data / max_rating
    test_data_norm = test_data / max_rating

    # L'autoencoder viene addestrato per 50 cicli su tutti i dati, mescolandoli ogni volta
    autoencoder.fit(
        train_data_norm,
        train_data_norm,
        epochs=epochs,
        batch_size=batch_size,
        validation_data=(test_data_norm, test_data_norm),
        shuffle=True
    )
    
    print("\n[✔️ ] Autoencoder allenato con successo.")

def get_recommendations(user_id, top_n=10):
    """Genera raccomandazioni per un dato utente."""
    global autoencoder, rating_matrix, restaurants_df

    if autoencoder is None or rating_matrix is None or restaurants_df is None:
        print("\n[❌] Errore: Il modello non è stato allenato. Eseguire train_autoencoder() prima di ottenere raccomandazioni.")
        return

    try:
        user_ratings = rating_matrix[user_id].reshape(1, -1)
    except IndexError:
        print(f"\n[❌] Errore: ID utente {user_id} non valido.")
        return

    # Normalizzo le valutazioni dell'utente
    max_rating = np.max(rating_matrix)
    user_ratings_norm = user_ratings / max_rating if max_rating > 0 else user_ratings

    # Predizione delle valutazioni per tutti i ristoranti.
    predicted_ratings = autoencoder.predict(user_ratings_norm)
    
    # Ottengo gli ID dei ristoranti raccomandati ordinando le predizioni in ordine decrescente.
    recommended_restaurants_ids = (-predicted_ratings).argsort()[0][:top_n]

    # Rimozione dei ristoranti già piaciuti dall'utente (valutazione >= 4).
    liked_restaurants_ids = np.where(rating_matrix[user_id] >= 4)[0]
    recommended_restaurants_ids = [r_id for r_id in recommended_restaurants_ids if r_id not in liked_restaurants_ids]
    if not recommended_restaurants_ids:
        print("\n[ℹ️] Nessun nuovo ristorante da consigliare. L'utente ha già valutato positivamente tutti i ristoranti predetti.")
        return

    # Ottengo i dettagli dei ristoranti raccomandati e piaciuti dal dataframe.
    recommended_restaurants = restaurants_df.iloc[recommended_restaurants_ids]
    liked_restaurants = restaurants_df.iloc[liked_restaurants_ids].head(3)

    # Stampo i ristoranti piaciuti.
    print("Dato che ti piacciono:")
    for _, row in liked_restaurants.iterrows():
        print(f"- {row['name']}")

    # Stampo i ristoranti raccomandati.
    print("\nPotrebbero piacerti anche:")
    for idx, (_, row) in enumerate(recommended_restaurants.iterrows(), start=1):
        print(f"{idx}. {row['name']}")