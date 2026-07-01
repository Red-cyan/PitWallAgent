from app.schemas.rules import RetrievedChunk


class RuleRepository:
    def search_relevant_chunks(self, question: str) -> list[RetrievedChunk]:
        normalized_question = question.lower()

        if "unsafe release" in normalized_question:
            return self._unsafe_release_chunks()

        if "parc ferme" in normalized_question or "parc fermé" in normalized_question:
            return self._parc_ferme_chunks()

        if "plank" in normalized_question or "skid block" in normalized_question:
            return self._plank_chunks()

        return self._default_chunks()

    def _unsafe_release_chunks(self) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                chunk_id="fia-sporting-article-34-5-page-72",
                content=(
                    "Cars may not be worked on in the fast lane in a manner that could endanger "
                    "drivers or team personnel. A car may be deemed to have been released in an "
                    "unsafe condition if it is sent from its pit stop in a way that creates a risk "
                    "to another competitor or pit lane personnel."
                ),
                score=0.95,
                document_title="FIA Formula One Sporting Regulations",
                article="Article 34.5",
                page=72,
            ),
            RetrievedChunk(
                chunk_id="fia-sporting-article-54-1-page-123",
                content=(
                    "The stewards may impose penalties when a competitor gains an advantage, causes "
                    "a collision, forces another driver off the track, or commits an unsafe act during "
                    "the competition."
                ),
                score=0.88,
                document_title="FIA Formula One Sporting Regulations",
                article="Article 54.1",
                page=123,
            ),
        ]

    def _parc_ferme_chunks(self) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                chunk_id="fia-sporting-parc-ferme-page-55",
                content=(
                    "After the qualifying session, cars are subject to parc ferme conditions. Under "
                    "these conditions, only specifically permitted work may be carried out on the car "
                    "unless approval is granted by the FIA technical delegate."
                ),
                score=0.94,
                document_title="FIA Formula One Sporting Regulations",
                article="Article 40.2",
                page=55,
            ),
            RetrievedChunk(
                chunk_id="fia-sporting-parc-ferme-exception-page-56",
                content=(
                    "Any change to the setup, suspension, aerodynamics, or other protected components "
                    "during parc ferme may lead to the car being required to start from the pit lane "
                    "unless explicitly authorized."
                ),
                score=0.86,
                document_title="FIA Formula One Sporting Regulations",
                article="Article 40.4",
                page=56,
            ),
        ]

    def _plank_chunks(self) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                chunk_id="fia-technical-plank-page-23",
                content=(
                    "The plank assembly must be fitted symmetrically about the car center line. Its "
                    "thickness is monitored after the session, and wear beyond the permitted limit may "
                    "constitute a breach of the technical regulations."
                ),
                score=0.93,
                document_title="FIA Formula One Technical Regulations",
                article="Article 3.5.9",
                page=23,
            ),
            RetrievedChunk(
                chunk_id="fia-technical-skid-page-24",
                content=(
                    "Skid block wear measurements are used to determine whether the plank has remained "
                    "within the minimum thickness requirements throughout the event."
                ),
                score=0.85,
                document_title="FIA Formula One Technical Regulations",
                article="Article 3.5.9.b",
                page=24,
            ),
        ]

    def _default_chunks(self) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                chunk_id="fia-general-procedure-page-12",
                content=(
                    "Competitors must comply with the sporting and technical regulations at all times "
                    "during the competition, and the FIA may investigate any suspected breach."
                ),
                score=0.72,
                document_title="FIA Formula One Sporting Regulations",
                article="Article 1.3",
                page=12,
            )
        ]
