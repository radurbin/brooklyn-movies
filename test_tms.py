from fetchers.alamo import AlamoFetcher
from fetchers.tms import TMSFetcher

movies = AlamoFetcher().fetch_movies()

movies = TMSFetcher().enrich(movies)

print()

for movie in movies[:5]:

    print(movie.title)
    print(movie.rating)
    print(movie.genres)
    print(movie.directors)
    print(movie.actors)
    print(movie.plot)
    print()
