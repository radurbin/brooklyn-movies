from fetchers.alamo import AlamoFetcher

fetcher = AlamoFetcher()

movies = fetcher.fetch_movies()

print()

for movie in movies[:5]:
    print(movie.title)
    print(len(movie.showtimes), "showtimes")
    print(movie.poster)
    print()
