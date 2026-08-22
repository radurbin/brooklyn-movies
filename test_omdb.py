from fetchers.alamo import AlamoFetcher
from fetchers.omdb import OMDbFetcher

movies = AlamoFetcher().fetch_movies()

movies = OMDbFetcher().enrich(movies)

print()

for movie in movies[:5]:

    print(movie.title)
    print(movie.imdb_rating)
    print(movie.rotten_tomatoes)
    print(movie.plot)
    print()