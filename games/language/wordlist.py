"""Built-in words (with clues) so Word Anagrams still works without internet access."""

OFFLINE_WORDS: dict[int, list[tuple[str, str]]] = {
    4: [
        ("lamp", "A device that gives light"),
        ("tree", "A tall plant with a trunk and branches"),
        ("moon", "Earth's natural satellite"),
        ("bird", "An animal with feathers and wings"),
        ("fish", "A cold-blooded animal that lives and swims in water"),
        ("rain", "Water that falls from clouds"),
        ("gold", "A precious yellow metal"),
        ("door", "An entrance you open and close"),
    ],
    5: [
        ("apple", "A round fruit that grows on trees, often red or green"),
        ("river", "A large natural stream of flowing water"),
        ("chair", "A seat with a back for one person"),
        ("cloud", "A white or grey mass floating in the sky"),
        ("bread", "A baked food made from flour, often sliced"),
        ("train", "A vehicle that runs on rails"),
        ("music", "Sounds arranged to please the ear"),
        ("plant", "A living thing that grows in soil and makes its own food"),
    ],
    6: [
        ("garden", "A piece of ground where flowers or vegetables are grown"),
        ("window", "An opening in a wall that lets in light"),
        ("planet", "A large body that orbits a star"),
        ("bridge", "A structure that carries a road over water or a valley"),
        ("forest", "A large area covered with trees"),
        ("school", "A place where children go to learn"),
        ("winter", "The coldest season of the year"),
        ("market", "A place where goods are bought and sold"),
    ],
    7: [
        ("kitchen", "The room where food is cooked"),
        ("mystery", "Something that is hard to explain or understand"),
        ("journey", "An act of travelling from one place to another"),
        ("science", "The study of the natural world through observation and experiment"),
        ("weather", "The state of the atmosphere: sun, rain, wind and so on"),
        ("library", "A place where books are kept to be read or borrowed"),
        ("rainbow", "An arc of colours seen in the sky after rain"),
        ("teacher", "A person whose job is to help others learn"),
    ],
    8: [
        ("mountain", "A very high natural elevation of the earth's surface"),
        ("elephant", "The largest land animal, with a trunk and tusks"),
        ("computer", "An electronic machine that processes information"),
        ("notebook", "A book of blank pages for writing notes"),
        ("sunshine", "The light and warmth that come from the sun"),
        ("backpack", "A bag carried on the back"),
        ("football", "A team sport played with a round ball and two goals"),
        ("umbrella", "A folding canopy used as protection against rain"),
    ],
    9: [
        ("adventure", "An exciting or unusual experience"),
        ("chocolate", "A sweet brown food made from cocoa beans"),
        ("telescope", "An instrument for viewing distant objects such as stars"),
        ("butterfly", "An insect with large, colourful wings"),
        ("pineapple", "A tropical fruit with a spiky skin and sweet yellow flesh"),
        ("furniture", "Tables, chairs and beds that make a room usable"),
        ("knowledge", "Facts and skills gained through learning or experience"),
        ("happiness", "The state of feeling joy"),
    ],
    10: [
        ("playground", "An outdoor area where children play"),
        ("lighthouse", "A tower with a bright light that guides ships"),
        ("strawberry", "A sweet red fruit with tiny seeds on its skin"),
        ("basketball", "A team sport in which players shoot a ball through a hoop"),
        ("friendship", "The bond between people who like and trust each other"),
        ("photograph", "A picture taken with a camera"),
        ("understand", "To grasp the meaning of something"),
        ("waterfalls", "Streams of water that drop from a height over rocks"),
    ],
}


def offline_words(length: int) -> list[dict]:
    """Built-in words of exactly `length` letters, in the same shape the word API returns."""
    return [{"word": w, "clue": c} for w, c in OFFLINE_WORDS.get(length, [])]
